import pytest

from findsl.official.domain import EventSpec, IndicatorRef, UniverseSpec
from findsl.official.domain.binder import DomainBindingError, bind_function
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official.types import NUMERIC
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot


def _typed_call(source):
    ast = parse_official_slot(source, mode="strict")
    return OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(ast)


@pytest.mark.parametrize(
    "source",
    [
        "indicator('沪|深', '', '涨幅', '今日', '', '', '')",
        "rank('', '', '涨幅', 'desc', '今日', '', '', '')",
        "belong_industry('', '', '涨幅', '今日', '')",
        "queryData('', '', '涨幅', '今日', '')",
        "cross_above('', '', '涨幅', '成交量', '今日', '', '')",
        "cross_down('', '', '涨幅', '成交量', '今日', '', '')",
        "close_together('', '', '涨幅', '成交量', '今日', '', '')",
        "reset('', '', '涨幅', '成交量', '今日', '', '')",
        "golden_cross('', '', '涨幅', '成交量', '今日', '', '')",
        "record_high('', '', '涨幅', '20日', '今日', '', '', '')",
        "record_low('', '', '涨幅', '20日', '今日', '', '', '')",
        "position('', '', '涨幅', '20日', '今日', '', '', '')",
    ],
)
def test_all_official_function_families_bind_to_domain_semantics(source):
    bound = bind_function(_typed_call(source), default_official_registry())

    assert bound.requirement.domains
    assert bound.function_name
    assert bound.market_scope.markets


def test_cross_function_binds_event_operands():
    bound = bind_function(
        _typed_call("cross_above('', '', '涨幅', '成交量', '今日', '', '')"),
        default_official_registry(),
    )
    assert isinstance(bound.expression, EventSpec)
    assert isinstance(bound.expression.left, IndicatorRef)


def test_market_expression_is_carried_as_typed_domain_contract():
    bound = bind_function(
        _typed_call("indicator('沪|深&^创业板', '', '成交量', '', '', '', '')"),
        default_official_registry(),
    )

    payload = bound.to_dict()
    assert payload["market_expression"]["kind"] == "MarketOr"
    assert "创业板" in str(payload["market_expression"])


def test_empty_indicator_binds_only_as_explicit_universe_capability():
    bound = bind_function(
        _typed_call("indicator('沪', '', '', '今日', '', '', '')"),
        default_official_registry(),
    )

    assert isinstance(bound.expression, UniverseSpec)
    assert bound.indicators == ()
    assert bound.requirement.domains == frozenset({"quote"})
    assert "scan" in bound.requirement.capabilities
    assert bound.to_dict()["expression"] == {
        "kind": "UniverseSpec",
        "domain": "quote",
        "selector": "all",
        "type": {"kind": "string"},
    }


def test_empty_query_data_indicator_is_not_misclassified_as_universe():
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(
            _typed_call("queryData('', '', '', '今日', '')"),
            default_official_registry(),
        )

    assert excinfo.value.code == "DOMAIN_CAPABILITY_UNSUPPORTED"


def test_empty_rank_indicator_binds_deterministic_stable_order_policy():
    bound = bind_function(
        _typed_call("rank('', '', '', 'desc', '', '', '', '')"),
        default_official_registry(),
    )

    assert bound.indicators[0].indicator_id == "稳定证券顺序"
    assert bound.indicators[0].type is NUMERIC
    assert bound.requirement.capabilities == frozenset({"scan", "stable_order"})


@pytest.mark.parametrize(
    "source, expected_slot",
    [
        ("cross_above('', '', '', '20日均线', '', '', '')", "indicator_name_1"),
        ("cross_down('', '', '', '20日均线', '', '', '')", "indicator_name_1"),
        ("close_together('', '', '', '20日均线', '', '', '')", "indicator_name_1"),
        ("reset('', '', '', '20日均线', '', '', '')", "indicator_name_1"),
        ("record_high('', '', '', '20日', '', '', '', '')", "indicator_name"),
        ("record_low('', '', '', '20日', '', '', '', '')", "indicator_name"),
        ("position('', '', '', '历史', '', '', '', '')", "indicator_name"),
    ],
)
def test_price_event_functions_bind_documented_empty_indicator_default(
    source, expected_slot
):
    typed = _typed_call(source)
    bound = bind_function(typed, default_official_registry())

    assert bound.indicators[0].indicator_id == "最新价"
    assert typed.binding.slots[expected_slot] == ""


def test_empty_event_right_indicator_remains_unsupported():
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(
            _typed_call("cross_above('', '', '', '', '', '', '')"),
            default_official_registry(),
        )

    assert excinfo.value.code == "DOMAIN_CAPABILITY_UNSUPPORTED"


def test_unknown_indicator_has_precise_diagnostic():
    typed = _typed_call("indicator('', '', '不存在指标', '今日', '', '', '')")
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(typed, default_official_registry())
    assert excinfo.value.code == "DOMAIN_UNKNOWN_INDICATOR"
    assert excinfo.value.slot == "indicator_name"


@pytest.mark.parametrize(
    "indicator,unit",
    [("11日均线", "currency"), ("34日均量线", "shares"), ("850日均线", "currency")],
)
def test_parameterized_moving_average_binds_as_prefix_derived_indicator(
    indicator, unit
):
    bound = bind_function(
        _typed_call(f"indicator('', '', '{indicator}', '', '', '', '')"),
        default_official_registry(),
    )

    assert bound.indicators[0].indicator_id == indicator
    assert bound.indicators[0].unit == unit
    assert "prefix_average" in bound.requirement.capabilities


def test_declared_missing_indicator_reports_data_unavailable():
    typed = _typed_call("indicator('', '', '营业收入', '今日', '', '', '')")
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(typed, default_official_registry())
    assert excinfo.value.code == "DOMAIN_DATA_UNAVAILABLE"


def test_invalid_rank_direction_has_precise_diagnostic():
    typed = _typed_call("rank('', '', '涨幅', 'sideways', '今日', '', '', '')")
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(typed, default_official_registry())
    assert excinfo.value.code == "DOMAIN_INVALID_ENUM"


def test_count_expression_binds_as_typed_temporal_contract():
    bound = bind_function(
        _typed_call("indicator('', '', '涨幅', '最近10日', '', '', 'CONS=3日')"),
        default_official_registry(),
    )

    assert bound.temporal is not None
    assert bound.temporal.mode == "CONS"
    assert bound.temporal.threshold == 3
    assert bound.temporal.unit == "日"
    assert bound.to_dict()["temporal"]["semantics"] == "trading_sequence"


def test_invalid_count_expression_preserves_temporal_diagnostic():
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(
            _typed_call("indicator('', '', '涨幅', '最近10日', '', '', 'CONS=0日')"),
            default_official_registry(),
        )

    assert excinfo.value.code == "TEMPORAL_CONSECUTIVE_THRESHOLD_INVALID"
    assert excinfo.value.slot == "count_exp"


@pytest.mark.parametrize(
    "date,kind,amount,unit",
    [
        ("这五天", "recent_sessions", 5, "session"),
        ("过去6天", "recent_sessions", 6, "session"),
        ("近3个交易日", "recent_sessions", 3, "session"),
        ("两年内", "recent_calendar", 2, "year"),
        ("近两月", "recent_calendar", 2, "month"),
        ("近半年", "recent_calendar", 6, "month"),
        ("半年内", "recent_calendar", 6, "month"),
        ("近五周", "recent_calendar", 5, "week"),
        ("本季度", "dynamic_period", None, "quarter"),
        ("上个月", "dynamic_period", None, "month"),
        ("前年", "dynamic_period", None, "year"),
        ("一八年", "calendar_range", None, "year"),
        ("2024年8月", "calendar_range", None, "month"),
        ("18年-24年", "calendar_range", None, "year"),
        ("2011年3月25日", "exact", None, None),
        ("昨天", "relative_session", 1, "session"),
        ("上个交易日", "relative_session", 1, "session"),
        ("上一交易日", "relative_session", 1, "session"),
        ("前天", "relative_session", 2, "session"),
        ("当天", "relative", None, None),
        ("目前", "relative", None, None),
        ("四天", "recent_sessions", 4, "session"),
        ("最近连续7个交易日", "recent_sessions", 7, "session"),
        ("前5日", "session_slice", 5, "session"),
        ("近半个月", "recent_calendar", 15, "day"),
        ("3个交易日前", "relative_session", 3, "session"),
        ("连续6天", "recent_sessions", 6, "session"),
        ("近3个季度", "recent_calendar", 9, "month"),
    ],
)
def test_date_slot_binds_to_typed_window_contract(date, kind, amount, unit):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == kind
    assert bound.date_constraint.amount == amount
    assert bound.date_constraint.unit == unit
    if date == "一八年":
        assert (bound.date_constraint.start, bound.date_constraint.end) == (
            "2018-01-01",
            "2018-12-31",
        )
    elif date == "2024年8月":
        assert (bound.date_constraint.start, bound.date_constraint.end) == (
            "2024-08-01",
            "2024-08-31",
        )
    elif date == "18年-24年":
        assert (bound.date_constraint.start, bound.date_constraint.end) == (
            "2018-01-01",
            "2024-12-31",
        )
    elif date == "2011年3月25日":
        assert (bound.date_constraint.start, bound.date_constraint.end) == (
            "2011-03-25",
            "2011-03-25",
        )


@pytest.mark.parametrize(
    "date,kind,offset,month,day",
    [
        ("本月", "dynamic_period", 0, None, None),
        ("上周", "dynamic_period", -1, None, None),
        ("去年", "dynamic_period", -1, None, None),
        ("前年", "dynamic_period", -2, None, None),
        ("7月", "anchor_calendar", 0, 7, None),
        ("3月2号", "anchor_calendar", 0, 3, 2),
        ("8号", "anchor_calendar", 0, None, 8),
    ],
)
def test_dynamic_date_contract_preserves_anchor_components(date, kind, offset, month, day):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == kind
    assert bound.date_constraint.offset == offset
    assert bound.date_constraint.month == month
    assert bound.date_constraint.day == day


@pytest.mark.parametrize(
    ("date", "kind", "month", "end_month"),
    [
        ("上半年", "year_month_range", 1, 6),
        ("今年二季度", "year_month_range", 4, 6),
        ("3-7月", "year_month_range", 3, 7),
        ("Q2", "year_month_range", 4, 6),
    ],
)
def test_current_year_ranges_keep_both_month_boundaries(
    date, kind, month, end_month
):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == kind
    assert bound.date_constraint.month == month
    assert bound.date_constraint.end_month == end_month


@pytest.mark.parametrize(
    ("date", "normalized"),
    [
        ("2025/5/7", "2025-05-07"),
        ("20260313", "2026-03-13"),
        ("2026.3.13", "2026-03-13"),
    ],
)
def test_alternate_exact_date_formats_are_normalized(date, normalized):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert (bound.date_constraint.start, bound.date_constraint.end) == (
        normalized,
        normalized,
    )


@pytest.mark.parametrize(
    "date,start,end",
    [
        ("20240101-20241231", "2024-01-01", "2024-12-31"),
        ("2024年1月1日至2024年3月31日", "2024-01-01", "2024-03-31"),
        ("2022-2025年", "2022-01-01", "2025-12-31"),
        ("2024年第二季度", "2024-04-01", "2024-06-30"),
        ("2024Q3", "2024-07-01", "2024-09-30"),
        ("2023年第四季度至2024年第一季度", "2023-10-01", "2024-03-31"),
    ],
)
def test_explicit_calendar_ranges_are_normalized(date, start, end):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == "calendar_range"
    assert (bound.date_constraint.start, bound.date_constraint.end) == (start, end)


@pytest.mark.parametrize(
    "date,kind,month,day,end_month,end_day,unit,offset,start",
    [
        ("4月20日-6月16日", "month_day_range", 4, 20, 6, 16, "day", 0, None),
        ("本月7日到13日", "month_day_range", None, 7, None, 13, "day", 0, None),
        ("八日到二十二日", "month_day_range", None, 8, None, 22, "day", 0, None),
        ("年初至今", "dynamic_period", None, None, None, None, "year", 0, None),
        ("月初至今", "dynamic_period", None, None, None, None, "month", 0, None),
        ("上月至今", "period_since", None, None, None, None, "month", -1, None),
        ("今年4月份以来", "anchor_since", 4, 1, None, None, "day", 0, None),
        ("9.24以来", "anchor_since", 9, 24, None, None, "day", 0, None),
        ("2024年10月1日至今", "calendar_since", None, None, None, None, "day", 0, "2024-10-01"),
    ],
)
def test_open_ended_and_month_day_ranges_are_typed(
    date, kind, month, day, end_month, end_day, unit, offset, start
):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    constraint = bound.date_constraint
    assert constraint.kind == kind
    assert constraint.month == month
    assert constraint.day == day
    assert constraint.end_month == end_month
    assert constraint.end_day == end_day
    assert constraint.unit == unit
    assert constraint.offset == offset
    assert constraint.start == start


@pytest.mark.parametrize(
    "date,kind,start,offset,amount",
    [
        ("一二年的第4年", "calendar_range", "2015-01-01", 0, None),
        ("7月的前1月", "anchor_calendar", None, -1, None),
        ("昨日的第二天", "relative", None, 0, None),
        ("昨日的前1日", "session_slice", None, 2, 1),
        ("最近三天的前3日", "session_slice", None, 3, 3),
        ("过去10个交易日内", "recent_sessions", None, 0, 10),
        ("本周的前3天", "before_period_sessions", None, 0, 3),
        ("2024年3月10号的后5日", "after_date_sessions", "2024-03-10", 0, 5),
    ],
)
def test_composite_date_phrases_preserve_relative_session_semantics(
    date, kind, start, offset, amount
):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == kind
    assert bound.date_constraint.start == start
    assert bound.date_constraint.offset == offset
    assert bound.date_constraint.amount == amount


@pytest.mark.parametrize(
    ("date", "kind", "amount", "unit", "offset", "month", "day", "end_month"),
    [
        ("2025年5月6日的前1日", "before_date_sessions", 1, "session", 0, None, None, None),
        ("昨天至今", "session_slice", 2, "session", 0, None, None, None),
        ("近15个工作日", "recent_sessions", 15, "session", 0, None, None, None),
        ("本月开始12日", "from_period_sessions", 12, "month", 0, None, None, None),
        ("连续四季度", "rolling_periods", 4, "quarter", 0, None, None, None),
        ("去年一季度", "year_month_range", None, "month", -1, 1, None, 3),
        ("二三季度", "year_month_range", None, "month", 0, 4, None, 9),
        ("本月13日", "anchor_calendar", None, "day", 0, None, 13, None),
        ("9月10月", "year_month_range", None, "month", 0, 9, None, 10),
        ("9月28号开始", "anchor_since", None, "day", 0, 9, 28, None),
        ("今年年初", "from_period_sessions", 1, "year", 0, None, None, None),
        ("4月30号的当月", "anchor_calendar", None, "month", 0, 4, None, None),
        ("3年前", "shifted_calendar_session", 1, "year", -3, None, None, None),
        ("一周前", "shifted_calendar_session", 1, "week", -1, None, None, None),
        ("上周五最后一个交易日", "period_end_session", 1, "week", -1, None, None, None),
        ("今年3月的后2月", "year_month_range", None, "month", 0, 4, None, 5),
        ("周四周五", "dynamic_weekday_range", None, "week", 0, None, None, None),
        ("大前天后3日", "session_slice", 3, "session", 0, None, None, None),
        ("去年9月初", "from_anchor_sessions", 1, "session", -12, 9, 1, None),
    ],
)
def test_generalized_calendar_algebra_preserves_typed_contracts(
    date, kind, amount, unit, offset, month, day, end_month
):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    constraint = bound.date_constraint
    assert constraint.kind == kind
    assert constraint.amount == amount
    assert constraint.unit == unit
    assert constraint.offset == offset
    assert constraint.month == month
    assert constraint.day == day
    assert constraint.end_month == end_month


def test_ambiguous_non_contiguous_quarter_shorthand_is_not_invented():
    bound = bind_function(
        _typed_call("indicator('', '', '涨幅', '一四季度', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == "expression"


def test_weekday_session_algebra_keeps_week_anchor_and_direction():
    bound = bind_function(
        _typed_call("indicator('', '', '涨幅', '上周三开始4日', '', '', '')"),
        default_official_registry(),
    )

    constraint = bound.date_constraint
    assert constraint.kind == "from_weekday_sessions"
    assert constraint.amount == 4
    assert constraint.offset == -1
    assert constraint.weekday_start == 3


@pytest.mark.parametrize(
    "date,kind,start,end,offset,amount,month,day",
    [
        (
            "2012年的后4年",
            "calendar_range",
            "2013-01-01",
            "2016-12-31",
            0,
            4,
            None,
            None,
        ),
        ("今天的前1日", "session_slice", None, None, 1, 1, None, None),
        ("9号的前1日", "before_anchor_sessions", None, None, 0, 1, None, 9),
        ("3月9号的后3日", "after_anchor_sessions", None, None, 0, 3, 3, 9),
    ],
)
def test_extended_date_algebra_preserves_typed_boundaries(
    date,
    kind,
    start,
    end,
    offset,
    amount,
    month,
    day,
):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == kind
    assert bound.date_constraint.start == start
    assert bound.date_constraint.end == end
    assert bound.date_constraint.offset == offset
    assert bound.date_constraint.amount == amount
    assert bound.date_constraint.month == month
    assert bound.date_constraint.day == day


@pytest.mark.parametrize(
    "date",
    [
        "2024年13月",
        "2024年2月30日",
        "2024-02-30",
        "2024年第四季度至2024年第一季度",
        "20241231-20240101",
        "周五到周一",
        "6月20日到4月10日",
        "本月20日到10日",
    ],
)
def test_invalid_calendar_date_is_rejected_with_stable_domain_code(date):
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(
            _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
            default_official_registry(),
        )

    assert excinfo.value.code == "DOMAIN_DATE_INVALID"


@pytest.mark.parametrize(
    ("source", "offset", "start", "end"),
    [
        ("上周二至周四", -1, 2, 4),
        ("本周一至周五", 0, 1, 5),
        ("本周一到本周三", 0, 1, 3),
        ("上上周一到周四", -2, 1, 4),
        ("周三到周五", 0, 3, 5),
    ],
)
def test_weekday_ranges_are_typed_without_row_specific_rules(source, offset, start, end):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{source}', '', '', '')"),
        default_official_registry(),
    )

    constraint = bound.date_constraint
    assert constraint.kind == "dynamic_weekday_range"
    assert constraint.offset == offset
    assert constraint.weekday_start == start
    assert constraint.weekday_end == end


@pytest.mark.parametrize(
    ("source", "kind", "amount"),
    [
        ("最近的第一天", "relative", None),
        ("最近的第二天", "relative_session", 1),
        ("最近的第5个交易日", "relative_session", 4),
    ],
)
def test_latest_ordinal_sessions_use_trading_session_offsets(source, kind, amount):
    bound = bind_function(
        _typed_call(f"indicator('', '', '涨幅', '{source}', '', '', '')"),
        default_official_registry(),
    )

    assert bound.date_constraint.kind == kind
    assert bound.date_constraint.amount == amount
