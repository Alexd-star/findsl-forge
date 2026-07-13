import pytest

from conftest import OFFICIAL_WORKBOOK, external_file_available
from findsl.official_frontend_evidence import build_frontend_evidence


@pytest.mark.skipif(not external_file_available(OFFICIAL_WORKBOOK), reason="official workbook is external")
def test_evidence_counts_all_official_rows_and_latency_percentiles():
    report = build_frontend_evidence(OFFICIAL_WORKBOOK, sample_size=3)

    assert report["row_count"] == 5799
    assert sum(report["recovery"]["classifications"].values()) == 5799
    assert report["input_sha256"]
    assert report["recovery"]["latency_ms"]["antlr"]["p95"] >= 0
    assert report["strict"]["handwritten_parse_ok"] == 5792
    assert report["recovery"]["handwritten_parse_ok"] == 5799
    assert report["migration_gate"]["passed"] is True
    assert report["migration_gate"]["blocking_divergences"] == 0
    assert report["migration_gate"]["diagnostic_only_divergences"] == 1
