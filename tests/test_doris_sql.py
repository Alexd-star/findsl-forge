from findsl import Compiler
from findsl.doris_sql import validate_doris_select_sql


def test_compiler_attaches_doris_sql_validation_explain_step():
    result = Compiler().compile('filter(SUM(indicator("volume"), 3) > 300)')

    validation_steps = [step for step in result.explain if step["rule"] == "DORIS_SQL_VALIDATION"]
    assert validation_steps
    assert validation_steps[0]["status"] == "applied"
    assert validation_steps[0]["evidence"]["issue_count"] == 0
    assert "dwd_stock_daily_quote_prefix" in validation_steps[0]["evidence"]["table_references"]


def test_doris_sql_validator_rejects_multi_statement_sql():
    result = validate_doris_select_sql("SELECT * FROM dwd_stock_daily_quote; DROP TABLE dwd_stock_daily_quote")

    assert not result.passed
    assert {issue.code for issue in result.issues} >= {"MULTI_STATEMENT_SQL", "FORBIDDEN_STATEMENT_TOKEN"}


def test_doris_sql_validator_rejects_unknown_table_references():
    result = validate_doris_select_sql("SELECT * FROM surprise_table")

    assert not result.passed
    assert any(issue.code == "UNKNOWN_TABLE_REFERENCE" for issue in result.issues)


def test_doris_sql_validator_rejects_window_functions_inside_where():
    result = validate_doris_select_sql(
        "SELECT * FROM dwd_stock_daily_quote WHERE AVG(close) OVER (PARTITION BY ts_code) > 10"
    )

    assert not result.passed
    assert any(issue.code == "WINDOW_IN_WHERE" for issue in result.issues)


def test_doris_sql_validator_ignores_comment_markers_inside_string_literals():
    result = validate_doris_select_sql("SELECT * FROM dwd_stock_daily_quote WHERE market = 'A--safe'")

    assert result.passed
    assert result.issues == []
