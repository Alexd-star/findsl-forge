from findsl.official.corpus_audit import (
    build_corpus_audit,
    render_corpus_audit_markdown,
)
from findsl.official.service import OfficialCompilerService


def test_corpus_audit_separates_data_invalid_and_ledger_repair():
    ledger_source = "rank('其他&法', '', '市盈率', 'desc', '', '', '', '') > 0\""
    rows = [
        {
            "excel_row": 2,
            "source": "indicator('', '', '成交量', '今日', '', '', '') > 1",
            "new_backend_success": True,
            "terminal_stage": "backend",
            "terminal_code": "PASS",
        },
        {
            "excel_row": 3,
            "source": "indicator('', '', '营业收入', '', '', '', '') > 1",
            "new_backend_success": False,
            "terminal_stage": "typed",
            "terminal_code": "OFFICIAL_TYPE_ERROR",
        },
        {
            "excel_row": 4,
            "source": "indicator('', '', '涨幅', '最近', '', '', '') > 1",
            "new_backend_success": False,
            "terminal_stage": "physical",
            "terminal_code": "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED",
        },
        {
            "excel_row": 5328,
            "source": ledger_source,
            "new_backend_success": False,
            "terminal_stage": "frontend",
            "terminal_code": "OFFICIAL_ANTLR_LEX_ERROR",
        },
    ]

    report = build_corpus_audit(
        {
            "git_head": "a" * 40,
            "source_sha256": "b" * 64,
            "row_count": len(rows),
            "rows": rows,
        },
        OfficialCompilerService(),
    )

    assert report["baseline_status_counts"] == {
        "INVALID_INPUT": 3,
        "SUPPORTED": 1,
    }
    by_row = {item["excel_row"]: item for item in report["rows"]}
    assert by_row[3]["root_cause"] == "dataset_snapshot_required"
    assert by_row[4]["root_cause"] == "ambiguous_date"
    assert by_row[5328]["root_cause"] == "registered_syntax_anomaly"
    assert by_row[5328]["safe_repair"]["requires_confirmation"] is True
    assert "不能为了覆盖率" in render_corpus_audit_markdown(report)


def test_corpus_audit_infers_missing_indicator_type_without_enabling_it():
    source = "indicator('', '', '基本每股收益', '', '', '', '') > 1"
    report = build_corpus_audit(
        {
            "git_head": "a" * 40,
            "source_sha256": "b" * 64,
            "row_count": 1,
            "rows": [
                {
                    "excel_row": 2,
                    "source": source,
                    "new_backend_success": False,
                    "terminal_stage": "typed",
                    "terminal_code": "OFFICIAL_TYPE_ERROR",
                }
            ],
        },
        OfficialCompilerService(),
    )

    row = report["rows"][0]
    contract = next(
        item
        for item in report["indicator_contracts"]
        if item["indicator_name"] == "基本每股收益"
    )
    assert row["indicator_type_evidence"]["基本每股收益"] == ["numeric"]
    assert contract["suggested_value_type"] == "numeric"
    assert row["must_reject_without_confirmation"] is True


def test_corpus_audit_keeps_new_data_inference_out_of_historical_baseline():
    source = "indicator('港', '', '收盘价', '', '概念', '', '') > 10"
    report = build_corpus_audit(
        {
            "git_head": "a" * 40,
            "source_sha256": "b" * 64,
            "row_count": 1,
            "rows": [
                {
                    "excel_row": 2,
                    "source": source,
                    "new_backend_success": False,
                    "terminal_stage": "physical",
                    "terminal_code": "PHYSICAL_GROUP_BOUND_UNSUPPORTED",
                }
            ],
        },
        OfficialCompilerService(),
    )

    assert report["baseline_status_counts"] == {"CAPABILITY_GAP": 1}
    assert report["current_status_counts"] == {"DATA_UNAVAILABLE": 1}


def test_corpus_audit_accepts_frozen_historical_status_by_row():
    source = "indicator('', '', '成交量', '今日', '', '', '') > 1"
    report = build_corpus_audit(
        {
            "git_head": "a" * 40,
            "source_sha256": "b" * 64,
            "row_count": 1,
            "rows": [
                {
                    "excel_row": 2,
                    "source": source,
                    "new_backend_success": True,
                    "terminal_stage": "backend",
                    "terminal_code": "PASS",
                }
            ],
        },
        OfficialCompilerService(),
        baseline_status_by_row={2: "INVALID_INPUT"},
    )

    assert report["baseline_status_counts"] == {"INVALID_INPUT": 1}
    assert report["current_status_counts"] == {"SUPPORTED": 1}
