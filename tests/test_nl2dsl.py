from findsl.compiler import Compiler
from findsl.nl2dsl import suggest_dsl


def test_suggests_consecutive_inflow_rank_dsl_from_chinese_request():
    result = suggest_dsl("筛选A股连续三天主力净流入为正并按换手率排名前一百")

    assert not result.warnings
    top = result.top
    assert top is not None
    assert top.rule == "consecutive_inflow_rank"
    assert top.dsl == (
        'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), '
        'rank(indicator("turnover_rate"), desc, top=100))'
    )
    assert top.confidence >= 0.9
    assert "ROW_NUMBER()" in Compiler().compile(top.dsl).sql


def test_suggests_low_turnover_rank_with_bottom_limit_when_order_is_ascending():
    result = suggest_dsl("筛选A股连续三天主力净流入为正并按换手率从低到高排名前十")

    assert result.top is not None
    assert result.top.rule == "consecutive_inflow_rank"
    assert result.top.dsl == (
        'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), '
        'rank(indicator("turnover_rate"), asc, bottom=10))'
    )
    assert "ORDER BY turnover_rate ASC" in Compiler().compile(result.top.dsl).sql


def test_suggests_money_flow_low_price_bottom_rank():
    result = suggest_dsl("A股存在资金流入后按低价取每日2只")

    assert result.top is not None
    assert result.top.rule == "money_flow_low_price_rank"
    assert result.top.dsl == (
        'then(filter(market("A") & EXIST(indicator("main_net_inflow") > 0, 2)), '
        'rank(indicator("close"), asc, bottom=2))'
    )
    compiled = Compiler().compile(result.top.dsl)
    assert "ORDER BY close ASC" in compiled.sql
    assert "rank_no <= 2" in compiled.sql


def test_suggests_turnover_percent_rank():
    result = suggest_dsl("A股每日换手率前50%")

    assert result.top is not None
    assert result.top.rule == "turnover_percent_rank"
    assert result.top.dsl == 'then(filter(market("A")), rank(indicator("turnover_rate"), desc, percent=50))'
    assert "__partition_count" in Compiler().compile(result.top.dsl).sql


def test_suggests_high_turnover_close_rank():
    result = suggest_dsl("A股高换手后按收盘价取每日前2")

    assert result.top is not None
    assert result.top.rule == "high_turnover_close_rank"
    assert result.top.dsl == (
        'then(filter(market("A") & indicator("turnover_rate") > 1), '
        'rank(indicator("close"), desc, top=2))'
    )
    assert "ORDER BY close DESC" in Compiler().compile(result.top.dsl).sql


def test_suggests_signed_net_outflow_threshold():
    result = suggest_dsl("主力净流出低于-1.5")

    assert result.top is not None
    assert result.top.rule == "net_outflow_threshold"
    assert result.top.dsl == 'filter(indicator("main_net_inflow") < -1.5)'
    assert "main_net_inflow < -1.5" in Compiler().compile(result.top.dsl).sql


def test_suggests_outflow_magnitude_as_negative_threshold():
    result = suggest_dsl("主力净流出超过2")

    assert result.top is not None
    assert result.top.dsl == 'filter(indicator("main_net_inflow") < -2)'


def test_suggests_close_new_high_with_chinese_window_number():
    result = suggest_dsl("今日收盘价创二百五十日新高")

    assert result.top is not None
    assert result.top.dsl == 'filter(indicator("close") >= MAX(indicator("close"), 250))'
    assert "MAX(close) OVER" in Compiler().compile(result.top.dsl).sql


def test_suggests_close_rolling_min_threshold():
    result = suggest_dsl("近3日最低收盘价低于10")

    assert result.top is not None
    assert result.top.rule == "close_rolling_min_threshold"
    assert result.top.dsl == 'filter(MIN(indicator("close"), 3) < 10)'
    assert "MIN(close) OVER" in Compiler().compile(result.top.dsl).sql


def test_suggests_volume_breakout_exists_template():
    result = suggest_dsl("近10日存在放量")

    assert result.top is not None
    assert result.top.dsl == 'filter(EXIST(indicator("volume") > MA(indicator("volume"), 20), 10))'


def test_suggests_rolling_sum_and_formats_unit_threshold_as_plain_number():
    result = suggest_dsl("近3日成交量累计大于300万")

    assert result.top is not None
    assert result.top.dsl == 'filter(SUM(indicator("volume"), 3) > 3000000)'
    assert "3e" not in result.top.dsl
    assert "dwd_stock_daily_quote_prefix" in Compiler().compile(result.top.dsl).sql


def test_suggests_date_range_rolling_sum_with_prefix_pruning():
    result = suggest_dsl("2026-01-02到2026-01-04近3日成交量累计大于300")

    assert result.top is not None
    assert result.top.rule == "date_range_rolling_volume_sum"
    assert result.top.dsl == (
        'filter(date_between("2026-01-02", "2026-01-04") '
        '& SUM(indicator("volume"), 3) > 300)'
    )
    compiled = Compiler().compile(result.top.dsl)
    assert "dwd_stock_daily_quote_prefix" in compiled.sql
    assert "DATE_RANGE_PREFIX_PRUNING" in {step["rule"] for step in compiled.explain}


def test_suggests_date_range_close_threshold():
    result = suggest_dsl("2026-01-02到2026-01-04收盘价大于10")

    assert result.top is not None
    assert result.top.rule == "date_range_close_threshold"
    assert result.top.dsl == 'filter(date_between("2026-01-02", "2026-01-04") & indicator("close") > 10)'
    compiled = Compiler().compile(result.top.dsl)
    assert "trade_date >= '2026-01-02'" in compiled.sql
    assert "DATE_RANGE_PUSHDOWN" in {step["rule"] for step in compiled.explain}


def test_suggests_date_range_close_above_ma_without_confusing_window_for_threshold():
    result = suggest_dsl("2026-01-02到2026-01-04收盘价大于3日均线")

    assert result.top is not None
    assert result.top.rule == "date_range_close_above_ma"
    assert result.top.dsl == (
        'filter(date_between("2026-01-02", "2026-01-04") '
        '& indicator("close") > MA(indicator("close"), 3))'
    )
    compiled = Compiler().compile(result.top.dsl)
    assert "AVG(close) OVER" in compiled.sql
    assert "close > 3" not in compiled.sql
    assert "DATE_RANGE_WINDOW_PRUNING" in {step["rule"] for step in compiled.explain}


def test_reports_warning_when_no_template_matches():
    result = suggest_dsl("找出形态非常好看的股票")

    assert result.candidates == []
    assert result.warnings == ["no high-confidence template matched the request"]
