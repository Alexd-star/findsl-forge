from findsl.official_frontend_evidence import build_frontend_evidence


OFFICIAL_WORKBOOK = (
    r"D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\选股 DSL 规范文档\选股提槽实例.xlsx"
)


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
