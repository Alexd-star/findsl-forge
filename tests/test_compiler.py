from findsl import Compiler


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
    assert "COUNT(*) OVER (PARTITION BY trade_date) AS __partition_count" in result.sql
    assert "rank_no <= CAST(((__partition_count * 50) + 99.999999) / 100.0 AS INTEGER)" in result.sql
    rank_steps = [step for step in result.explain if step["rule"] == "RANK_ROW_NUMBER"]
    assert rank_steps[0]["evidence"]["limit_kind"] == "percent"
    assert rank_steps[0]["evidence"]["limit_value"] == 50.0
