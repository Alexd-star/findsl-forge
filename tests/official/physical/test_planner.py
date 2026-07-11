import pytest

from findsl.official.lowering import lower_official_ast
from findsl.official.physical import PhysicalFilter, PhysicalIn, PhysicalLimit, PhysicalRank
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.planner import PhysicalPlanningError, plan_physical
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot


def _lower(source):
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parse_official_slot(source, mode="strict"))
    return lower_official_ast(typed, domain_registry=default_official_registry())


def test_direct_indicator_candidate_is_selected_with_trace():
    result = plan_physical(_lower("indicator('', '', '成交量', '', '', '', '') > 100"), default_physical_catalog())

    assert isinstance(result.plan, PhysicalFilter)
    assert result.selected_resource == "official_basic"
    assert result.decisions[0].feasible is True
    assert result.decisions[0].estimated is True


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
