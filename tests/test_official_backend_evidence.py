from findsl.official_backend_evidence import audit_official_backend_sources


def test_backend_evidence_separates_grounded_sql_from_unavailable_domains():
    report = audit_official_backend_sources(
        [
            "indicator('', '', '成交量', '', '', '', '') > 100",
            "indicator('', '', '涨幅', '', '', '', '') > 1",
            "indicator('', '', '营业收入', '今日', '', '', '') > 1",
        ],
        sample_size=5,
    )

    assert report["row_count"] == 3
    assert report["typed_ok"] == 3
    assert report["logical_ok"] == 2
    assert report["physical_ok"] == 1
    assert report["sqlglot_ok"] == 1
    assert report["safety_ok"] == 1
    assert report["errors"]["PHYSICAL_PLAN_UNAVAILABLE"] == 1
    assert report["errors"]["DOMAIN_DATA_UNAVAILABLE"] == 1
    assert report["static_gate"]["passed"] is True
    assert report["real_doris_execution"]["status"] == "NOT_RUN"
