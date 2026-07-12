import pytest

from findsl.official.lowering import lower_official_ast
from findsl.official.physical import PhysicalAggregateRank, PhysicalCompositeAggregate, PhysicalFilter, PhysicalGroupedAggregate, PhysicalIn, PhysicalJoin, PhysicalLimit, PhysicalNthLatestValue, PhysicalPrefixAverage, PhysicalRank, PhysicalRecentSessions, PhysicalSetOperation, PhysicalTableScan, PhysicalTemporal
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.expressions import default_physical_expressions
from findsl.official.physical.planner import PhysicalPlanningError, plan_physical
from findsl.official.physical.statistics import PhysicalStatisticsSnapshot, default_physical_statistics
from findsl.official.physical.strategies import default_physical_strategies
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot


def _lower(source):
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parse_official_slot(source, mode="strict"))
    return lower_official_ast(typed, domain_registry=default_official_registry())


def _statistics(catalog, resources):
    return PhysicalStatisticsSnapshot.from_dict(
        {
            "schema_version": 1,
            "catalog_sha256": catalog.fingerprint,
            "collected_at": "2026-07-11T16:00:00+08:00",
            "doris_version": "4.1.0",
            "resources": resources,
        },
        catalog,
    )


def test_direct_indicator_candidate_is_selected_with_trace():
    result = plan_physical(_lower("indicator('', '', '成交量', '', '', '', '') > 100"), default_physical_catalog())

    assert isinstance(result.plan, PhysicalFilter)
    assert result.selected_resource == "official_basic"
    assert result.decisions[0].feasible is True
    assert result.decisions[0].estimated is True


def test_real_statistics_replace_priority_with_auditable_scan_bytes():
    catalog = default_physical_catalog()
    statistics = _statistics(
        catalog,
        [
            {
                "resource_id": "official_basic",
                "row_count": 13650347,
                "data_size_bytes": 411096137,
                "row_count_available": True,
            }
        ],
    )

    result = plan_physical(
        _lower("indicator('', '', '成交量', '', '', '', '') > 100"),
        catalog,
        statistics=statistics,
    )

    decision = result.decisions[0]
    assert decision.cost == 411096137.0
    assert decision.cost_unit == "bytes"
    assert decision.cost_components == (("official_basic", 411096137.0),)
    assert decision.estimated is False
    assert decision.reason_code == "PHYSICAL_STATISTICS_CANDIDATE_SELECTED"


def test_anchored_resource_cost_includes_primary_and_anchor_scan_bytes():
    catalog = default_physical_catalog()
    statistics = _statistics(
        catalog,
        [
            {"resource_id": "official_basic", "row_count": 10, "data_size_bytes": 400, "row_count_available": True},
            {"resource_id": "official_ext", "row_count": 8, "data_size_bytes": 300, "row_count_available": True},
        ],
    )

    result = plan_physical(
        _lower("indicator('', '', '主力净流入', '', '', '', '') > 0"),
        catalog,
        statistics=statistics,
    )

    assert result.decisions[0].cost == 700.0
    assert result.decisions[0].cost_components == (
        ("official_ext", 300.0),
        ("official_basic", 400.0),
    )


def test_incomplete_statistics_fall_back_to_explicit_estimated_priority():
    catalog = default_physical_catalog()
    statistics = _statistics(
        catalog,
        [
            {"resource_id": "official_ext", "row_count": 8, "data_size_bytes": 300, "row_count_available": True},
        ],
    )

    result = plan_physical(
        _lower("indicator('', '', '主力净流入', '', '', '', '') > 0"),
        catalog,
        statistics=statistics,
    )

    decision = result.decisions[0]
    assert decision.cost == 20.0
    assert decision.cost_unit == "catalog_priority"
    assert decision.cost_components == ()
    assert decision.estimated is True
    assert decision.reason_code == "PHYSICAL_STATISTICS_INCOMPLETE"


def test_limit_is_preserved_in_physical_plan():
    result = plan_physical(_lower("indicator('', '', '成交量', '', '', '', '') > 100 limit 0,20"), default_physical_catalog())
    assert isinstance(result.plan, PhysicalLimit)
    assert result.plan.count == 20


def test_derived_or_missing_indicator_is_not_faked():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(_lower("indicator('', '', '涨幅', '', '', '', '') > 1"), default_physical_catalog())
    assert excinfo.value.code == "PHYSICAL_PLAN_UNAVAILABLE"
    assert excinfo.value.decisions[0].feasible is False
    assert excinfo.value.decisions[0].reason_code == "PHYSICAL_MAPPING_MISSING"


def test_technical_indicator_selects_controlled_technical_resource_deterministically():
    source = "indicator('', '', '10日均线', '', '', '', '') > 10"

    first = plan_physical(_lower(source), default_physical_catalog())
    second = plan_physical(_lower(source), default_physical_catalog())

    assert first.selected_resource == "official_technical"
    assert first.decisions == second.decisions
    assert first.decisions[0].cost == 20.0


def test_statistics_rank_prefix_candidate_but_keep_uncalibrated_strategy_in_shadow():
    catalog = default_physical_catalog()
    statistics = default_physical_statistics(catalog)

    result = plan_physical(
        _lower("indicator('', '', '5日均线', '', '', '', '') > 10"),
        catalog,
        statistics=statistics,
        strategies=default_physical_strategies(catalog),
    )

    assert result.selected_resource == "official_technical"
    assert result.selected_strategy == "direct_column"
    assert isinstance(result.plan, PhysicalFilter)
    assert [decision.strategy_id for decision in result.decisions] == [
        "direct_column",
        "ma5_prefix_average",
    ]
    assert result.decisions[0].selected is True
    assert result.decisions[1].selection_eligible is False
    assert result.decisions[1].cost < result.decisions[0].cost


def test_shadow_prefix_candidate_can_be_selected_for_explicit_validation():
    catalog = default_physical_catalog()
    result = plan_physical(
        _lower("indicator('', '', '5日均线', '', '', '', '') > 10"),
        catalog,
        statistics=default_physical_statistics(catalog),
        strategies=default_physical_strategies(catalog),
        allow_shadow_strategies=True,
    )

    assert result.selected_strategy == "ma5_prefix_average"
    assert isinstance(result.plan.predicate.left, PhysicalPrefixAverage)
    assert result.plan.predicate.left.window == 5


def test_approximate_comparison_without_catalog_tolerance_is_rejected_before_backend():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower("indicator('', '', '成交量', '', '', '', '') ~= 100"),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_APPROXIMATION_POLICY_MISSING"


@pytest.mark.parametrize(
    "source",
    [
        "indicator('', '软件开发', '成交量', '', '', '', '') > 100",
        "indicator('', '', '成交量', '', 'AVG', '', '') > 100",
    ],
)
def test_unmaterialized_function_constraints_are_never_silently_dropped(source):
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(_lower(source), default_physical_catalog())

    assert excinfo.value.code == "PHYSICAL_CONSTRAINT_UNSUPPORTED"


@pytest.mark.parametrize("aggregate", ["SUM", "AVG", "MAX", "MIN"])
def test_single_aggregate_lowers_to_grouped_set_plan(aggregate):
    result = plan_physical(
        _lower(
            f"indicator('沪', '', '成交量', '近5日', '', '{aggregate}', '') > 100"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalGroupedAggregate)
    assert result.plan.function == aggregate.lower()
    assert result.plan.comparator == ">"
    assert result.plan.bound.value == 100
    assert result.selected_strategy == "grouped_aggregate"


def test_growth_aggregate_is_not_approximated_as_sum_or_scalar_field():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower(
                "indicator('', '', '成交量', '近5日', '', 'GROWTH_RISE', '') > 10"
            ),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED"


def test_multiple_aggregate_measures_lower_to_named_relations_and_outer_predicate():
    result = plan_physical(
        _lower(
            "indicator('', '', '主力净流入', '近5日', '', 'AVG', '') / "
            "indicator('', '', '成交额', '近5日', '', 'AVG', '') < 20%"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalCompositeAggregate)
    assert len(result.plan.groups) == 2
    assert [group.alias for group in result.plan.groups] == ["aggregate_0", "aggregate_1"]
    assert result.selected_strategy == "composite_grouped_aggregate"
    assert "PhysicalAggregateRef" in result.plan.predicate.canonical_json()
    assert "PhysicalNullIf" in result.plan.predicate.canonical_json()


def test_identical_aggregate_call_is_materialized_once_and_reused():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '近5日', '', 'SUM', '') > 10 and "
            "indicator('', '', '成交量', '近5日', '', 'SUM', '') < 1000000000"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalCompositeAggregate)
    assert len(result.plan.groups) == 1
    assert result.plan.predicate.canonical_json().count("PhysicalAggregateRef") == 2


def test_scalar_snapshot_and_window_aggregate_use_one_typed_composite_plan():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '今日', '', '', '') = "
            "indicator('', '', '成交量', '近100个交易日', '', 'MIN', '')"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalCompositeAggregate)
    assert len(result.plan.groups) == 1
    payload = result.plan.canonical_json()
    assert "PhysicalLatestValue" in payload
    assert "PhysicalRecentSessions" in payload


def test_composite_aggregate_rejects_conflicting_scalar_snapshot_dates():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower(
                "indicator('', '', '成交量', '今日', '', '', '') + "
                "indicator('', '', '成交额', '昨日', '', '', '') > "
                "indicator('', '', '成交量', '近5日', '', 'AVG', '')"
            ),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_SCALAR_SCOPE_MISMATCH"


def test_growth_rank_keeps_a_dedicated_unsupported_contract():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower("rank('', '', '成交量', 'desc', '', '', 'GROWTH_RISE', '') <= 10"),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED"


def test_latest_date_and_market_constraints_are_materialized_in_predicate():
    result = plan_physical(
        _lower("indicator('沪|深', '', '成交量', '今日', '', '', '') > 100"),
        default_physical_catalog(),
    )

    payload = result.plan.to_dict()
    assert payload["kind"] == "PhysicalFilter"
    assert "PhysicalLatestValue" in result.plan.canonical_json()
    assert "mktcode" in result.plan.canonical_json()


@pytest.mark.parametrize("market,expected", [("深", 0), ("沪", 1), ("京", 103)])
def test_market_codes_follow_official_doris_protocol(market, expected):
    result = plan_physical(
        _lower(f"indicator('{market}', '', '成交量', '', '', '', '') > 100"),
        default_physical_catalog(),
    )
    market_constraint = result.plan.predicate.right
    assert isinstance(market_constraint, PhysicalIn)
    assert [item.value for item in market_constraint.values] == [expected]


@pytest.mark.parametrize(
    "market,prefixes",
    [
        ("科创板", ("688",)),
        ("创业板", ("300", "301")),
        ("沪主板", ("600", "601", "603", "605")),
        ("深主板", ("000", "001", "002", "003")),
    ],
)
def test_board_market_constraints_use_controlled_code_ranges(market, prefixes):
    result = plan_physical(
        _lower(f"indicator('{market}', '', '成交量', '', '', '', '') > 100"),
        default_physical_catalog(),
    )

    payload = result.plan.canonical_json()
    for prefix in prefixes:
        assert f'{prefix}000' in payload
        assert f'{prefix}999' in payload
    assert "kcbFlag" not in payload
    assert "gemFlag" not in payload


def test_unavailable_official_market_is_not_compiled_as_empty_result():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower("indicator('港', '', '成交量', '', '', '', '') > 100"),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_MARKET_DATA_UNAVAILABLE"


def test_security_resource_uses_basic_anchor_for_stable_date_key():
    result = plan_physical(
        _lower("indicator('', '', '股票名称', '', '', '', '') = '华泰%'"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert result.plan.input.anchor_resource_id == "official_basic"


def test_resource_without_date_column_uses_anchor_date_constraint():
    result = plan_physical(
        _lower("indicator('', '', '股票名称', '今日', '', '', '') = '华泰%'"),
        default_physical_catalog(),
    )

    assert "official_basic" in result.plan.canonical_json()


@pytest.mark.parametrize(
    "date,start,end",
    [
        ("一八年", "2018-01-01", "2018-12-31"),
        ("2024年8月", "2024-08-01", "2024-08-31"),
        ("2011年3月25日", "2011-03-25", "2011-03-25"),
    ],
)
def test_typed_calendar_constraints_lower_without_reparsing_date_fragments(date, start, end):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '{date}', '', '', '') > 100"),
        default_physical_catalog(),
    )

    payload = result.plan.canonical_json()
    assert start in payload
    assert end in payload
    assert "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED" not in payload


@pytest.mark.parametrize("date,offset", [("昨天", 1), ("昨日", 1), ("前天", 2), ("前一个交易日", 1)])
def test_relative_session_date_lowers_to_trading_calendar_offset(date, offset):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '{date}', '', '', '') > 100"),
        default_physical_catalog(),
    )

    date_predicate = result.plan.predicate.right
    assert isinstance(date_predicate.right, PhysicalNthLatestValue)
    assert date_predicate.right.offset == offset


@pytest.mark.parametrize("date,amount", [("近5日", 5), ("最近十个交易日", 10), ("30个交易日内", 30)])
def test_recent_session_range_lowers_to_typed_calendar_membership(date, amount):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '{date}', '', '', '') > 100"),
        default_physical_catalog(),
    )

    date_predicate = result.plan.predicate.right
    assert isinstance(date_predicate, PhysicalRecentSessions)
    assert date_predicate.amount == amount


def test_direct_numeric_rank_lowers_with_comparison_contract():
    result = plan_physical(
        _lower("rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalRank)
    assert result.plan.direction == "desc"
    assert result.plan.comparator == "<="
    assert result.plan.bound.value == 10


def test_percentage_rank_preserves_partition_fraction_contract():
    result = plan_physical(
        _lower("rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10%"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalRank)
    assert result.plan.percentage is True
    assert result.plan.bound.value == 10


def test_aggregate_rank_groups_measure_before_window_ranking():
    result = plan_physical(
        _lower("rank('', '', '成交量', 'desc', '近5日', '', 'AVG', '') <= 10"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalAggregateRank)
    assert result.plan.function == "avg"
    assert result.plan.direction == "desc"
    assert result.plan.bound.value == 10
    assert result.selected_strategy == "aggregate_rank"


def test_rank_and_scalar_predicate_plan_as_stable_set_intersection():
    result = plan_physical(
        _lower(
            "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10 and "
            "indicator('', '', '成交额', '今日', '', '', '') > 100"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalSetOperation)
    assert result.plan.operation == "intersect"
    assert isinstance(result.plan.left, PhysicalRank)
    assert isinstance(result.plan.right, PhysicalFilter)


def test_limit_wrapped_rank_intersection_preserves_relational_limit():
    result = plan_physical(
        _lower(
            "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10 and "
            "indicator('', '', '成交额', '今日', '', '', '') > 100 limit 0,3"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalLimit)
    assert isinstance(result.plan.input, PhysicalSetOperation)
    assert result.plan.count == 3


def test_query_data_uses_the_same_controlled_direct_field_mapping():
    result = plan_physical(
        _lower("queryData('', '', '成交量', '', '') > 100"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert result.selected_resource == "official_basic"


def test_universe_selector_uses_basic_scan_without_fake_indicator_column():
    result = plan_physical(
        _lower("indicator('沪', '', '', '今日', '', '', '') = 'all'"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert result.selected_resource == "official_basic"
    assert result.plan.input.columns == ()
    payload = result.plan.canonical_json()
    assert '"value":"all"' in payload
    assert "mktcode" in payload
    assert "PhysicalLatestValue" in payload


def test_universe_selector_rejects_non_all_comparison():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower("indicator('', '', '', '', '', '', '') = 'subset'"),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_UNIVERSE_COMPARISON_UNSUPPORTED"


def test_universe_selector_does_not_claim_unavailable_filter_scope_membership():
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(
            _lower("indicator('', '鸿蒙概念', '', '', '', '', '') = 'all'"),
            default_physical_catalog(),
        )

    assert excinfo.value.code == "PHYSICAL_CONSTRAINT_UNSUPPORTED"


def test_ext_scan_is_anchored_to_official_basic_universe():
    result = plan_physical(
        _lower("indicator('', '', '主力净流入', '', '', '', '') > 0"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert result.plan.input.anchor_resource_id == "official_basic"


def test_multi_resource_expression_builds_explicit_stable_key_join_tree():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '', '', '', '') > 0"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert isinstance(result.plan.input, PhysicalJoin)
    assert isinstance(result.plan.input.left, PhysicalTableScan)
    assert isinstance(result.plan.input.right, PhysicalTableScan)
    assert result.plan.input.left.resource_id == "official_basic"
    assert result.plan.input.right.resource_id == "official_ext"
    assert [(left.column, right.column) for left, right in result.plan.input.keys] == [
        ("mktcode", "mktcode"),
        ("tgtcode", "tgtcode"),
        ("bizdate", "bizdate"),
    ]
    assert result.selected_resource == "official_basic+official_ext"


def test_three_resource_join_uses_two_keys_for_static_security_dimension():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '', '', '', '') > 0 and "
            "indicator('', '', 'ST股票标识', '', '', '', '') = False"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    outer_join = result.plan.input
    assert isinstance(outer_join, PhysicalJoin)
    assert outer_join.right.resource_id == "official_security"
    assert [left.column for left, _ in outer_join.keys] == ["mktcode", "tgtcode"]
    assert isinstance(outer_join.left, PhysicalJoin)
    assert outer_join.left.right.resource_id == "official_ext"
    assert [left.column for left, _ in outer_join.left.keys] == [
        "mktcode",
        "tgtcode",
        "bizdate",
    ]
    assert result.selected_resource == "official_basic+official_ext+official_security"


def test_ext_market_constraint_binds_to_stable_anchor_resource():
    result = plan_physical(
        _lower("indicator('深', '', '主力净流入', '', '', '', '') > 0"),
        default_physical_catalog(),
    )

    assert result.plan.predicate.right.expression.resource_id == "official_basic"


def test_filter_then_rank_stage_lowers_operation_chain_once():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '', '', '', '') > 0 "
            "then rank('', '', '成交量', 'desc', '', '', '', '') <= 10"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalRank)
    assert isinstance(result.plan.input, PhysicalFilter)
    assert result.plan.canonical_json().count('"kind":"PhysicalScan"') == 1


def test_chained_rank_is_rejected_until_stage_alias_propagation_is_implemented():
    source = (
        "indicator('', '', '成交量', '', '', '', '') > 0 "
        "then rank('', '', '成交量', 'desc', '', '', '', '') <= 10 "
        "then rank('', '', '成交量', 'asc', '', '', '', '') <= 5"
    )
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(_lower(source), default_physical_catalog())

    assert excinfo.value.code == "PHYSICAL_CHAINED_RANK_UNSUPPORTED"


def test_rank_call_inside_scalar_expression_is_not_lowered_as_a_column():
    source = (
        "rank('', '', '连板天数', 'desc', '', '', '', '') + "
        "rank('', '', '跌停天数', 'desc', '', '', '', '') = 1"
    )
    with pytest.raises(PhysicalPlanningError) as excinfo:
        plan_physical(_lower(source), default_physical_catalog())

    assert excinfo.value.code == "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED"


@pytest.mark.parametrize(
    "source,resource,columns,node_kind",
    [
        ("indicator('', '', '最新价', '', '', '', '') > 1", "official_basic", {"lastPx"}, "PhysicalBinary"),
        ("indicator('', '', '涨幅', '', '', '', '') > 1", "official_basic", {"lastPx", "preClosePx"}, "PhysicalNullIf"),
        ("indicator('', '', '涨停', '', '', '', '') = True", "official_basic", {"limitFlag"}, "PhysicalComparison"),
        ("indicator('', '', '总市值', '', '', '', '') > 1", "official_basic", {"lastPx", "totalShare"}, "PhysicalBinary"),
        ("indicator('', '', '主力净流出', '', '', '', '') > 1", "official_ext", {"ZJLXMainNetTur"}, "PhysicalUnary"),
    ],
)
def test_controlled_derived_indicator_lowers_to_typed_physical_expression(
    source, resource, columns, node_kind
):
    catalog = default_physical_catalog()
    result = plan_physical(
        _lower(source),
        catalog,
        expressions=default_physical_expressions(catalog),
    )

    assert result.selected_resource == resource
    assert {column.column for column in result.plan.input.columns} == columns
    assert node_kind in result.plan.canonical_json()
    assert result.decisions[0].reason_code in {
        "PHYSICAL_CANDIDATE_SELECTED",
        "PHYSICAL_STATISTICS_CANDIDATE_SELECTED",
    }


def test_boolean_derived_indicator_preserves_explicit_true_comparison():
    catalog = default_physical_catalog()
    result = plan_physical(
        _lower("indicator('', '', '首板涨停', '', '', '', '') = True"),
        catalog,
        expressions=default_physical_expressions(catalog),
    )

    payload = result.plan.canonical_json()
    assert "PhysicalCoalesce" in payload
    assert "limitFlag" in payload
    assert "upSerialLb" in payload


@pytest.mark.parametrize(
    "count_exp,mode,threshold",
    [("EXIST>=5", "EXIST", 5), ("CONS=3日", "CONS", 3)],
)
def test_atomic_count_expression_lowers_to_explicit_physical_temporal_plan(count_exp, mode, threshold):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '', '', '', '{count_exp}') > 100"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalTemporal)
    assert result.plan.mode == mode
    assert result.plan.threshold == threshold
    assert result.plan.trading_sequence is True


def test_recent_days_temporal_window_is_normalized_to_trading_sessions():
    result = plan_physical(
        _lower("indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') > 100"),
        default_physical_catalog(),
    )

    assert result.plan.window.kind == "recent_sessions"
    assert result.plan.window.lookback_sessions == 10


@pytest.mark.parametrize("date,sessions", [("这五天", 5), ("过去6天", 6), ("近3个交易日", 3)])
def test_colloquial_trading_windows_are_typed_before_physical_planning(date, sessions):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '{date}', '', '', 'EXIST>0') > 100"),
        default_physical_catalog(),
    )

    assert result.plan.window.kind == "recent_sessions"
    assert result.plan.window.lookback_sessions == sessions


@pytest.mark.parametrize("date,amount,unit", [("两年内", 2, "year"), ("近两月", 2, "month")])
def test_calendar_temporal_windows_preserve_amount_and_unit(date, amount, unit):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '{date}', '', '', 'EXIST>0') > 100"),
        default_physical_catalog(),
    )

    assert result.plan.window.kind == "recent_calendar"
    assert result.plan.window.calendar_amount == amount
    assert result.plan.window.calendar_unit == unit


def test_same_scope_temporal_arithmetic_lowers_all_required_columns_once():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') / "
            "indicator('', '', '成交额', '最近10日', '', '', '') > 0"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalTemporal)
    assert {column.column for column in result.plan.input.columns} == {"volume", "turnover"}
    assert "PhysicalBinary" in result.plan.predicate.canonical_json()


def test_temporal_boolean_branches_lower_to_physical_set_operation():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '最近5日', '', '', 'EXIST>0') > 100 and "
            "indicator('', '', '成交额', '最近10日', '', '', 'CONS=3日') > 0"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalSetOperation)
    assert result.plan.operation == "intersect"
    assert isinstance(result.plan.left, PhysicalTemporal)
    assert isinstance(result.plan.right, PhysicalTemporal)


def test_temporal_set_operation_supports_independent_physical_resources():
    result = plan_physical(
        _lower(
            "indicator('', '', '成交量', '最近5日', '', '', 'EXIST>0') > 100 or "
            "indicator('', '', '主力净流入', '最近5日', '', '', 'EXIST>0') > 0"
        ),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalSetOperation)
    assert result.plan.operation == "union"
    assert {result.plan.left.input.resource_id, result.plan.right.input.resource_id} == {
        "official_basic",
        "official_ext",
    }


@pytest.mark.parametrize(
    "count_exp,unit",
    [
        ("CONS=每年", "年"),
        ("EXIST>=2月", "月"),
        ("CONS=3季度", "季度"),
        ("CONS=每周", "周"),
    ],
)
def test_calendar_bucket_temporal_units_reach_physical_ir(count_exp, unit):
    result = plan_physical(
        _lower(f"indicator('', '', '成交量', '两年内', '', '', '{count_exp}') > 100"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalTemporal)
    assert result.plan.unit == unit
    assert result.plan.window.kind == "recent_calendar"
