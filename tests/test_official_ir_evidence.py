import pytest

from conftest import OFFICIAL_WORKBOOK, external_file_available
from findsl.official_ir_evidence import build_official_ir_evidence


@pytest.mark.skipif(not external_file_available(OFFICIAL_WORKBOOK), reason="official workbook is external")
def test_official_ir_evidence_audits_all_rows_and_passes_internal_gate():
    report = build_official_ir_evidence(OFFICIAL_WORKBOOK, sample_size=3)

    assert report["row_count"] == 5799
    assert report["strict_parse_ok"] == 5792
    assert report["validated_plan_count"] == report["lowering_ok"]
    assert report["deterministic_hash_mismatches"] == 0
    assert report["gate"]["passed"] is True
    assert report["latency_ms"]["p95"] < 50
