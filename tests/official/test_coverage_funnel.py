from findsl.official_coverage_funnel import (
    build_official_coverage_funnel,
    render_official_coverage_funnel_markdown,
)


SOURCES = [
    "indicator('', '', '成交量', '', '', '', '') > 100",
    "indicator('', '', '营业收入', '', '', '', '') > 1",
    "indicator('', '', '3分钟涨速', '', '', '', '') > 1",
    "indicator(",
]


def test_coverage_funnel_uses_legacy_successes_as_migration_denominator():
    report = build_official_coverage_funnel(SOURCES)

    assert report["row_count"] == 4
    assert report["legacy_strict_success"] == 2
    assert report["new_backend_success"] == 1
    assert report["legacy_to_new_migrated"] == 1
    assert report["migration_coverage"] == 0.5
    assert report["stage_success"] == {
        "frontend": 3,
        "typed": 3,
        "logical": 2,
        "optimizer": 2,
        "physical": 1,
        "backend": 1,
    }


def test_coverage_funnel_records_terminal_codes_rows_and_function_families():
    report = build_official_coverage_funnel(SOURCES)

    assert report["terminal_errors"] == {
        "DOMAIN_DATA_UNAVAILABLE": 1,
        "PHYSICAL_PLAN_UNAVAILABLE": 1,
        "OFFICIAL_ANTLR_PARSE_ERROR": 1,
    }
    assert report["function_families"]["indicator"]["rows"] == 3
    assert report["function_families"]["indicator"]["new_backend_success"] == 1
    assert report["migration_gaps"][0]["code"] == "PHYSICAL_PLAN_UNAVAILABLE"
    assert report["migration_gaps"][0]["count"] == 1
    assert [row["excel_row"] for row in report["rows"]] == [2, 3, 4, 5]


def test_coverage_funnel_markdown_explains_denominator_and_next_priority():
    markdown = render_official_coverage_funnel_markdown(
        build_official_coverage_funnel(SOURCES)
    )

    assert "旧严格后端成功集" in markdown
    assert "50.00%" in markdown
    assert "PHYSICAL_PLAN_UNAVAILABLE" in markdown
    assert "不得把 4 条总语料直接作为 SQL 正确率分母" in markdown
