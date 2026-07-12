import pytest

from findsl.official.domain import EventSpec, IndicatorRef, UniverseSpec
from findsl.official.domain.binder import DomainBindingError, bind_function
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
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


def test_empty_rank_indicator_remains_unsupported_without_order_measure():
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(
            _typed_call("rank('', '', '', 'desc', '', '', '', '')"),
            default_official_registry(),
        )

    assert excinfo.value.code == "DOMAIN_CAPABILITY_UNSUPPORTED"


def test_unknown_indicator_has_precise_diagnostic():
    typed = _typed_call("indicator('', '', '不存在指标', '今日', '', '', '')")
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(typed, default_official_registry())
    assert excinfo.value.code == "DOMAIN_UNKNOWN_INDICATOR"
    assert excinfo.value.slot == "indicator_name"


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
        ("一八年", "calendar_range", None, "year"),
        ("2024年8月", "calendar_range", None, "month"),
        ("2011年3月25日", "exact", None, None),
        ("昨天", "relative_session", 1, "session"),
        ("前天", "relative_session", 2, "session"),
        ("当天", "relative", None, None),
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
    elif date == "2011年3月25日":
        assert (bound.date_constraint.start, bound.date_constraint.end) == (
            "2011-03-25",
            "2011-03-25",
        )


@pytest.mark.parametrize("date", ["2024年13月", "2024年2月30日"])
def test_invalid_calendar_date_is_rejected_with_stable_domain_code(date):
    with pytest.raises(DomainBindingError) as excinfo:
        bind_function(
            _typed_call(f"indicator('', '', '涨幅', '{date}', '', '', '')"),
            default_official_registry(),
        )

    assert excinfo.value.code == "DOMAIN_DATE_INVALID"
