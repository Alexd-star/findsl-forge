from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from findsl.official.context import CompileContext
from findsl.official.physical.catalog import PhysicalCatalog
from findsl.official.pipeline import OfficialPipelineError, compile_official
from findsl.official.signatures import FunctionCatalogError, OfficialFunctionCatalog


REPO_ROOT = Path(__file__).resolve().parents[2]
INDICATOR = "indicator('', '', '成交量', '今日', '', '', '')"


def test_configured_numeric_scalar_runs_through_official_main_pipeline() -> None:
    result = compile_official(f"abs_value({INDICATOR}) > 100").to_dict()

    assert "ABS(" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True
    assert result["backend"]["safety_passed"] is True
    assert result["typed_ast"]["children"][0]["binding"]["template_kind"] == "numeric_scalar"


def test_configured_safe_ratio_inserts_zero_division_guard() -> None:
    result = compile_official(f"safe_ratio({INDICATOR}, {INDICATOR}) > 1").to_dict()

    assert "NULLIF" in result["backend"]["sql"]
    physical = json.dumps(result["physical"]["plan"], ensure_ascii=False)
    assert "PhysicalNullIf" in physical


def test_configured_function_enforces_argument_types() -> None:
    with pytest.raises(OfficialPipelineError) as captured:
        compile_official("abs_value('not numeric') > 1")

    assert captured.value.stage == "typed"
    assert captured.value.code == "OFFICIAL_FUNCTION_ARG_TYPE"


def test_configured_alias_resolves_without_core_code_branch() -> None:
    result = compile_official(f"ABS_VALUE({INDICATOR}) > 100")

    assert "ABS(" in result.backend["sql"]


def test_configured_boolean_event_template_reuses_typed_physical_operators() -> None:
    result = compile_official(f"above_value({INDICATOR}, {INDICATOR}) = True").to_dict()

    assert ">" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


def test_blind_config_only_function_extension_keeps_core_tree_hash(tmp_path: Path) -> None:
    shutil.copytree(REPO_ROOT / "configs", tmp_path / "configs")
    before = _core_tree_hash(REPO_ROOT / "src/findsl/official")
    function_path = tmp_path / "configs/official/functions.json"
    payload = json.loads(function_path.read_text(encoding="utf-8"))
    payload["functions"].append(
        {
            "name": "sum_pair",
            "aliases": [],
            "argument_mode": "expressions",
            "arg_types": ["numeric", "numeric"],
            "result_kind": "numeric",
            "template_kind": "numeric_binary",
            "lowering_op": "add",
            "reference_op": "add",
            "version": "blind-test-v1",
        }
    )
    function_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    context = CompileContext.load(tmp_path)

    result = compile_official(f"sum_pair({INDICATOR}, {INDICATOR}) > 1", context=context)

    assert "+" in result.backend["sql"]
    assert _core_tree_hash(REPO_ROOT / "src/findsl/official") == before


def test_function_catalog_rejects_arbitrary_sql_template(tmp_path: Path) -> None:
    payload = json.loads(Path("configs/official/functions.json").read_text(encoding="utf-8"))
    payload["functions"][0]["sql_template"] = "DROP TABLE x"
    path = tmp_path / "functions.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FunctionCatalogError, match="fields"):
        OfficialFunctionCatalog.load(path)


def test_blind_config_only_indicator_extension_keeps_core_tree_hash(tmp_path: Path) -> None:
    shutil.copytree(REPO_ROOT / "configs", tmp_path / "configs")
    before = _core_tree_hash(REPO_ROOT / "src/findsl/official")
    indicator_path = tmp_path / "configs/official/indicators.json"
    indicators = json.loads(indicator_path.read_text(encoding="utf-8"))
    source = next(item for item in indicators if item["canonical_name"] == "成交量")
    new_indicator = dict(source)
    new_indicator["canonical_name"] = "盲测成交量副本"
    new_indicator["aliases"] = []
    indicators.append(new_indicator)
    indicator_path.write_text(json.dumps(indicators, ensure_ascii=False), encoding="utf-8")

    catalog_path = tmp_path / "configs/official/physical_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    source_field = next(item for item in catalog["fields"] if item["indicator_id"] == "成交量")
    new_field = dict(source_field)
    new_field["indicator_id"] = "盲测成交量副本"
    catalog["fields"].append(new_field)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    fingerprint = PhysicalCatalog.load(catalog_path).fingerprint
    for filename in ("physical_statistics.json", "physical_strategies.json"):
        path = tmp_path / "configs/official" / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["catalog_sha256"] = fingerprint
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    context = CompileContext.load(tmp_path)

    result = compile_official(
        "indicator('', '', '盲测成交量副本', '今日', '', '', '') > 1",
        context=context,
    )

    assert "`volume`" in result.backend["sql"]
    assert _core_tree_hash(REPO_ROOT / "src/findsl/official") == before


def _core_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
