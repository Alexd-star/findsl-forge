from pathlib import Path

from findsl.official.repair import OfficialRepairCatalog, default_repair_catalog


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_official_repair_catalog_loads_all_frozen_anomalies():
    catalog = OfficialRepairCatalog.load(
        REPO_ROOT / "configs/official/official_dsl_anomaly_ledger.json"
    )
    source = "and indicator('', '', '涨停未封板', '前天', '', '', '') = True"

    candidate = catalog.suggest(source)

    assert candidate is not None
    assert candidate.source_row == 5521
    assert candidate.candidate_dsl.startswith("indicator(")
    assert candidate.requires_confirmation is True
    assert candidate.auto_execute is False


def test_official_repair_catalog_requires_exact_source_match():
    assert default_repair_catalog().suggest(" indicator(") is None
