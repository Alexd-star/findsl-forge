import pytest

from findsl.official.lowering import lower_official_ast
from findsl.official.physical import PhysicalFilter, PhysicalLimit
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
