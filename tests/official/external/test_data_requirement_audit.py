from findsl.official.service import OfficialCompilerService
from scripts.audit_official_data_requirements import build_audit, render_markdown


def test_data_requirement_audit_separates_missing_data_and_invalid_semantics():
    rows = [
        {
            "excel_row": 1,
            "source": "indicator('', '', '营业收入', '', '', '', '') > 1",
            "new_backend_success": False,
        },
        {
            "excel_row": 2,
            "source": "indicator('', '', '涨幅', '最近', '', '', '') > 1",
            "new_backend_success": False,
        },
        {
            "excel_row": 3,
            "source": "indicator('', '', '成交量', '今日', '', '', '') > 1",
            "new_backend_success": True,
        },
    ]

    report = build_audit(
        {"rows": rows, "row_count": 3, "source_sha256": "a" * 64},
        OfficialCompilerService(),
    )

    assert report["status_counts"] == {
        "DATA_UNAVAILABLE": 1,
        "INVALID_INPUT": 1,
        "SUPPORTED": 1,
    }
    financial = next(
        item
        for item in report["data_domain_counts"]
        if item["domain_id"] == "financial_statement"
    )
    assert financial["profile_status"] == "not_loaded"
    assert "不能横向求和" in render_markdown(report)
