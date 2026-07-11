from pathlib import Path

import pytest

from findsl.official_domain_evidence import build_official_domain_evidence


OFFICIAL_WORKBOOK = (
    r"D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\选股 DSL 规范文档\选股提槽实例.xlsx"
)


@pytest.mark.skipif(not Path(OFFICIAL_WORKBOOK).is_file(), reason="official workbook is external")
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
