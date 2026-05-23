import pytest

from findsl import Compiler
from findsl.errors import SemanticError


def test_compile_then_generates_cte_and_rank():
    result = Compiler().compile('then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))')
    assert result.sql.startswith("WITH")
    assert "ROW_NUMBER()" in result.sql
    assert "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW" in result.sql
    assert "rank_no <= 100" in result.sql
    assert result.elapsed_ms < 50


def test_compile_max_window():
    result = Compiler().compile('filter(indicator("close") >= MAX(indicator("close"), 250))')
    assert "MAX(close) OVER" in result.sql
    assert "AS __win_1" in result.sql
    assert "ROWS BETWEEN 249 PRECEDING AND CURRENT ROW" in result.sql
    assert "WHERE close >= __win_1" in result.sql


def test_compile_exist_and_ma():
    result = Compiler().compile('filter(EXIST(indicator("volume") > MA(indicator("volume"), 20), 10))')
    assert "AVG(volume) OVER" in result.sql
    assert "AS __win_1" in result.sql
    assert "MAX(CASE WHEN volume > __win_1 THEN 1 ELSE 0 END) OVER" in result.sql
    assert "AS __roll_2" in result.sql
    assert "ROWS BETWEEN 9 PRECEDING AND CURRENT ROW" in result.sql
    assert "WHERE __roll_2 = 1" in result.sql


def test_compile_uses_left_joins_for_auxiliary_tables():
    result = Compiler().compile('filter(indicator("close") > 10 | indicator("main_net_inflow") > 0)')

    assert "LEFT JOIN dwd_stock_money_flow AS mf USING" in result.sql
    assert "close > 10 OR main_net_inflow > 0" in result.sql


def test_compile_uses_daily_quote_as_base_for_auxiliary_only_filters():
    result = Compiler().compile('filter(indicator("main_net_inflow") > 0)')

    assert "FROM dwd_stock_daily_quote AS base LEFT JOIN dwd_stock_money_flow AS mf USING" in result.sql
    assert "WHERE main_net_inflow > 0" in result.sql


def test_compile_excludes_null_rank_expressions_before_cutoff():
    result = Compiler().compile('rank(indicator("main_net_inflow"), desc, top=2)')

    assert "WHERE main_net_inflow IS NOT NULL" in result.sql
    assert any(step["rule"] == "RANK_NULL_GUARD" for step in result.explain)


def test_compile_sum_uses_prefix_sum_when_indicator_supports_it():
    result = Compiler().compile('filter(SUM(indicator("volume"), 3) > 300)')
    assert "dwd_stock_daily_quote_prefix" in result.sql
    assert "volume_prefix - COALESCE" in result.sql
    assert "__pref_prev_1.row_no = __pref_curr_1.row_no - 3" in result.sql
    assert "AS __psum_1" in result.sql
    assert "rewrite SUM() on volume into prefix-sum feature __psum_1" in result.trace
    prefix_steps = [step for step in result.explain if step["rule"] == "PREFIX_SUM"]
    assert prefix_steps[0]["status"] == "applied"
    assert prefix_steps[0]["evidence"]["indicator"] == "volume"
    assert prefix_steps[0]["evidence"]["prefix_table"] == "dwd_stock_daily_quote_prefix"


def test_compile_sum_falls_back_to_window_when_prefix_sum_is_not_supported():
    result = Compiler().compile('filter(SUM(indicator("close"), 3) > 30)')
    assert "SUM(close) OVER" in result.sql
    assert "dwd_stock_daily_quote_prefix" not in result.sql
    assert "rewrite SUM() into SUM window feature __win_1" in result.trace


def test_compile_can_disable_prefix_sum_optimizer():
    result = Compiler(enable_prefix_sum=False).compile('filter(SUM(indicator("volume"), 3) > 300)')
    assert "SUM(volume) OVER" in result.sql
    assert "dwd_stock_daily_quote_prefix" not in result.sql
    assert "rewrite SUM() into SUM window feature __win_1" in result.trace
    prefix_steps = [step for step in result.explain if step["rule"] == "PREFIX_SUM"]
    assert prefix_steps[0]["status"] == "skipped"
    assert prefix_steps[0]["evidence"]["reason"] == "disabled"


def test_compile_records_structured_explain_for_window_fallback():
    result = Compiler().compile('filter(SUM(indicator("close"), 3) > 30)')
    prefix_steps = [step for step in result.explain if step["rule"] == "PREFIX_SUM"]
    window_steps = [step for step in result.explain if step["rule"] == "WINDOW_FEATURE"]
    assert prefix_steps[0]["status"] == "skipped"
    assert prefix_steps[0]["evidence"]["reason"] == "unsupported_indicator"
    assert window_steps[0]["evidence"]["function"] == "SUM"


def test_compile_rank_percent_uses_partition_count_threshold():
    result = Compiler().compile('rank(indicator("turnover_rate"), desc, percent=50)')

    assert "ROW_NUMBER() OVER" in result.sql
    assert "ORDER BY turnover_rate DESC, ts_code ASC" in result.sql
    assert "COUNT(*) OVER (PARTITION BY trade_date) AS __partition_count" in result.sql
    assert "rank_no <= CAST(((__partition_count * 50) + 99.999999) / 100.0 AS INTEGER)" in result.sql
    rank_steps = [step for step in result.explain if step["rule"] == "RANK_ROW_NUMBER"]
    assert rank_steps[0]["evidence"]["limit_kind"] == "percent"
    assert rank_steps[0]["evidence"]["limit_value"] == 50.0


def test_compile_date_between_emits_trade_date_range_pushdown():
    result = Compiler().compile('filter(date_between("2026-01-02", "2026-01-04") & indicator("close") > 10)')

    assert "FROM dwd_stock_daily_quote AS base WHERE (trade_date >= '2026-01-02' AND trade_date <= '2026-01-04')" in result.sql
    assert "trade_date >= '2026-01-02'" in result.sql
    assert "trade_date <= '2026-01-04'" in result.sql
    assert "close > 10" in result.sql
    assert "rewrite date_between() into trade_date range predicate" in result.trace
    assert "push safe date range predicate into base scan" in result.trace
    date_steps = [step for step in result.explain if step["rule"] == "DATE_RANGE_PUSHDOWN"]
    assert date_steps[0]["status"] == "applied"
    assert date_steps[0]["evidence"]["start_date"] == "2026-01-02"
    base_steps = [step for step in result.explain if step["rule"] == "DATE_RANGE_BASE_PRUNING"]
    assert base_steps[0]["status"] == "applied"


def test_compile_date_between_prunes_window_queries_with_safe_upper_bound():
    result = Compiler().compile(
        'filter(date_between("2026-01-02", "2026-01-04") & indicator("close") > MA(indicator("close"), 3))'
    )

    assert "FROM dwd_stock_daily_quote AS base WHERE trade_date <= '2026-01-04'" in result.sql
    assert "FROM dwd_stock_daily_quote AS base WHERE (trade_date >=" not in result.sql
    assert "trade_date >= '2026-01-02'" in result.sql
    assert "push safe date upper bound into base scan for window context" in result.trace
    assert any(step["rule"] == "DATE_RANGE_PUSHDOWN" for step in result.explain)
    assert any(step["rule"] == "DATE_RANGE_WINDOW_PRUNING" for step in result.explain)
    assert not any(step["rule"] == "DATE_RANGE_BASE_PRUNING" for step in result.explain)


def test_compile_date_between_uses_full_pushdown_for_prefix_sum_windows():
    result = Compiler().compile(
        'filter(date_between("2026-01-02", "2026-01-04") & SUM(indicator("volume"), 3) > 300)'
    )

    assert "FROM dwd_stock_daily_quote AS base WHERE (trade_date >= '2026-01-02' AND trade_date <= '2026-01-04')" in result.sql
    assert "dwd_stock_daily_quote_prefix" in result.sql
    assert "push full date range into prefix-sum base scan" in result.trace
    assert any(step["rule"] == "DATE_RANGE_PREFIX_PRUNING" for step in result.explain)
    assert any(step["rule"] == "PREFIX_SUM" and step["status"] == "applied" for step in result.explain)
    assert not any(step["rule"] == "DATE_RANGE_WINDOW_PRUNING" for step in result.explain)


def test_compile_then_filter_filter_uses_stage_columns_without_inner_alias_leak():
    result = Compiler().compile('then(filter(market("A")), filter(indicator("close") > 10))')

    assert "stage2 AS" in result.sql
    assert "WHERE close > 10" in result.sql
    assert "WHERE base.close > 10" not in result.sql


def test_compile_then_filter_window_filter_materializes_feature_from_stage_columns():
    result = Compiler().compile('then(filter(market("A")), filter(MA(indicator("close"), 2) > 10))')

    assert "stage2 AS" in result.sql
    assert "AVG(close) OVER" in result.sql
    assert "WHERE __win_1 > 10" in result.sql
    assert "AVG(base.close) OVER" not in result.sql


def test_compile_rank_by_window_feature_materializes_sort_expression():
    result = Compiler().compile('rank(MA(indicator("close"), 2), desc, top=1)')

    assert "AVG(close) OVER" in result.sql
    assert "ORDER BY __win_1 DESC, ts_code ASC" in result.sql
    assert "FROM (SELECT rank_base_features.*" in result.sql
    assert "materialize rank numeric features before ranking" in result.trace
    assert any(
        step["rule"] == "FEATURE_LAYER"
        and step["evidence"].get("feature_count") == 1
        and "rank numeric features" in step["message"]
        for step in result.explain
    )


def test_compile_then_rank_by_window_feature_materializes_from_stage_columns():
    result = Compiler().compile('then(filter(market("A")), rank(MA(indicator("close"), 2), desc, top=1))')

    assert "stage2 AS" in result.sql
    assert "AVG(close) OVER" in result.sql
    assert "ORDER BY __win_1 DESC, ts_code ASC" in result.sql
    assert "AVG(base.close) OVER" not in result.sql


def test_compile_then_rank_filter_preserves_joined_relation_columns():
    result = Compiler().compile('then(rank(indicator("close"), desc, top=2), filter(market("A")))')

    assert "SELECT base.*, su.market AS market" in result.sql
    assert "WHERE market = 'A'" in result.sql
    assert "project joined relation columns before ranking" in result.trace
    assert any(step["rule"] == "RELATION_PROJECTION" for step in result.explain)


def test_compile_then_rank_rank_drops_previous_internal_rank_number():
    result = Compiler().compile(
        'then(rank(indicator("turnover_rate"), desc, top=2), rank(indicator("close"), asc, bottom=1))'
    )

    assert "project staged relation columns before re-ranking" in result.trace
    assert "base.rank_no" not in result.sql
    assert "base.volume AS volume FROM stage1 AS base" in result.sql
    assert result.sql.count("AS rank_no") == 2


def test_compile_escapes_string_literals_in_generated_sql():
    result = Compiler().compile('filter(market("A\' OR 1=1 --"))')

    assert "market = 'A'' OR 1=1 --'" in result.sql
    assert "market = 'A' OR 1=1 --'" not in result.sql


def test_compile_signed_numeric_threshold():
    result = Compiler().compile('filter(indicator("main_net_inflow") < -1.5)')

    assert "main_net_inflow < -1.5" in result.sql


def test_compile_normalizes_equality_operators_for_doris_sql():
    single_equal = Compiler().compile('filter(indicator("close") = 10)')
    equal = Compiler().compile('filter(indicator("close") == 10)')
    not_equal = Compiler().compile('filter(indicator("close") != 10)')

    assert "close = 10" in single_equal.sql
    assert "close = 10" in equal.sql
    assert "close == 10" not in equal.sql
    assert "close <> 10" in not_equal.sql
    assert "close != 10" not in not_equal.sql


def test_compile_rejects_top_level_numeric_expression_before_sql_generation():
    with pytest.raises(SemanticError, match="Top-level DSL"):
        Compiler().compile('indicator("close")')


def test_compile_accepts_case_insensitive_function_and_rank_limit_names():
    result = Compiler().compile('Then(Filter(market("A")), Rank(indicator("turnover_rate"), desc, TOP=2))')

    assert "WITH stage1 AS" in result.sql
    assert "rank_no <= 2" in result.sql


def test_compile_accepts_case_insensitive_indicator_names():
    result = Compiler().compile('filter(indicator("Close") > 10)')

    assert "close > 10" in result.sql
