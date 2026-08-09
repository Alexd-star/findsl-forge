import json
from pathlib import Path

import pytest

from findsl.official.context import CompileContext, CompileContextError
from findsl.official.external.profiles import DataProfileCatalog
from findsl.official.pipeline import OfficialPipelineError, compile_official


REPO_ROOT = Path(__file__).resolve().parents[3]
INDICATOR = "\u6210\u4ea4\u91cf"
TODAY = "\u4eca\u65e5"


def test_data_profile_catalog_exposes_official_and_enriched_modes() -> None:
    catalog = DataProfileCatalog.load(
        REPO_ROOT / "configs/official/data_profiles.json"
    )

    assert catalog.default_profile == "enriched_public"
    assert {profile.profile_id for profile in catalog.profiles()} == {
        "official_only",
        "enriched_public",
    }
    assert catalog.resolve("official_only").uses_external_data is False
    assert catalog.resolve("official_only").offline_reproducible is True
    assert catalog.resolve("enriched_public").offline_reproducible is False


def test_official_only_context_compiles_without_external_data() -> None:
    context = CompileContext.load(REPO_ROOT, data_profile="official_only")
    source = f"indicator('', '', '{INDICATOR}', '{TODAY}', '', '', '') > 0 limit 0,20"

    result = compile_official(source, context=context)

    assert context.snapshot.profile_id == "competition-official-only-v1"
    assert result.backend["sql"]
    assert context.physical_runtime.external_data_policy.industry is None
    assert context.physical_runtime.external_data_policy.instrument_rule is None


def test_official_only_rejects_a_scope_available_only_in_enriched_mode() -> None:
    enriched = CompileContext.load(REPO_ROOT, data_profile="enriched_public")
    official = CompileContext.load(REPO_ROOT, data_profile="official_only")
    runtime = json.loads(
        (REPO_ROOT / "configs/official/external_scope_runtime.json").read_text(
            encoding="utf-8"
        )
    )
    alias = next(
        item["alias"]
        for item in runtime["entries"]
        if item["scope_type"] in {"concept", "industry", "index"}
    )
    source = (
        f"indicator('', '{alias}', '{INDICATOR}', '{TODAY}', '', '', '') "
        "> 0 limit 0,20"
    )

    assert compile_official(source, context=enriched).backend["sql"]
    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(source, context=official)
    assert excinfo.value.code == "PHYSICAL_SCOPE_DATA_UNAVAILABLE"


def test_context_rejects_manifest_and_data_profile_together() -> None:
    with pytest.raises(CompileContextError, match="cannot be selected together"):
        CompileContext.load(
            REPO_ROOT,
            manifest_path=REPO_ROOT / "configs/official/compiler_manifest.json",
            data_profile="official_only",
        )


def test_explicit_manifest_takes_precedence_over_profile_environment(monkeypatch) -> None:
    monkeypatch.setenv("FINDSL_DATA_PROFILE", "official_only")

    context = CompileContext.load(
        REPO_ROOT,
        manifest_path=REPO_ROOT / "configs/official/compiler_manifest.json",
    )

    assert context.snapshot.profile_id == "competition-v1"


@pytest.mark.parametrize(
    ("source", "code"),
    (
        (
            "belong_industry('', '', '\u6210\u4ea4\u91cf', '', 'AVG') > 0 limit 0,20",
            "PHYSICAL_INDUSTRY_DATA_UNAVAILABLE",
        ),
        (
            "indicator('', '\u5f53\u5929\u4e70\u5f53\u5929\u5356', "
            "'\u662f\u5426T+0', '', '', '', '') = True limit 0,20",
            "PHYSICAL_INSTRUMENT_RULE_DATA_UNAVAILABLE",
        ),
    ),
)
def test_official_only_reports_optional_data_domain_by_type(source, code) -> None:
    context = CompileContext.load(REPO_ROOT, data_profile="official_only")

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(source, context=context)

    assert excinfo.value.code == code
