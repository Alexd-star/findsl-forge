import pytest

from conftest import OFFICIAL_WORKBOOK, external_file_available
from findsl.official_domain_evidence import build_official_domain_evidence


@pytest.mark.skipif(not external_file_available(OFFICIAL_WORKBOOK), reason="official workbook is external")
def test_domain_evidence_preserves_baselines_and_optimizer_invariants():
    report = build_official_domain_evidence(OFFICIAL_WORKBOOK, sample_size=3)

    assert report["row_count"] == 5799
    assert report["strict_parse_ok"] >= 5792
    assert report["strict_compile_ok"] >= 1097
    assert report["phase3_lowering_ok"] >= 2034
    assert report["optimized_validated"] == report["domain_lowering_ok"]
    assert report["idempotence_mismatches"] == 0
    assert report["gate"]["passed"] is True
    assert report["latency_ms"]["p95"] < 5
