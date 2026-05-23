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


def test_suggests_close_new_high_with_chinese_window_number():
    result = suggest_dsl("今日收盘价创二百五十日新高")

    assert result.top is not None
    assert result.top.dsl == 'filter(indicator("close") >= MAX(indicator("close"), 250))'
    assert "MAX(close) OVER" in Compiler().compile(result.top.dsl).sql


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


def test_suggests_date_range_close_threshold():
    result = suggest_dsl("2026-01-02到2026-01-04收盘价大于10")

    assert result.top is not None
    assert result.top.rule == "date_range_close_threshold"
    assert result.top.dsl == 'filter(date_between("2026-01-02", "2026-01-04") & indicator("close") > 10)'
    compiled = Compiler().compile(result.top.dsl)
    assert "trade_date >= '2026-01-02'" in compiled.sql
    assert "DATE_RANGE_PUSHDOWN" in {step["rule"] for step in compiled.explain}


def test_reports_warning_when_no_template_matches():
    result = suggest_dsl("找出形态非常好看的股票")

    assert result.candidates == []
    assert result.warnings == ["no high-confidence template matched the request"]
