import pytest

from findsl.official.lowering import lower_official_ast
from findsl.official.physical import PhysicalFilter, PhysicalIn, PhysicalLimit, PhysicalPrefixAverage, PhysicalRank
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


def test_direct_numeric_rank_lowers_with_comparison_contract():
    result = plan_physical(
        _lower("rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalRank)
    assert result.plan.direction == "desc"
    assert result.plan.comparator == "<="
    assert result.plan.bound.value == 10


def test_query_data_uses_the_same_controlled_direct_field_mapping():
    result = plan_physical(
        _lower("queryData('', '', '成交量', '', '') > 100"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert result.selected_resource == "official_basic"


def test_ext_scan_is_anchored_to_official_basic_universe():
    result = plan_physical(
        _lower("indicator('', '', '主力净流入', '', '', '', '') > 0"),
        default_physical_catalog(),
    )

    assert isinstance(result.plan, PhysicalFilter)
    assert result.plan.input.anchor_resource_id == "official_basic"


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
