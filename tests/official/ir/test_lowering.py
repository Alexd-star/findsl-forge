import pytest

from findsl.official.lowering import OfficialLoweringError, lower_official_ast
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import IndicatorMeta, parse_official_slot


def _resolver(name):
    return IndicatorMeta("basic", kind="numeric") if name in {"涨幅", "成交量"} else None


def _lower(source):
    ast = parse_official_slot(source, mode="strict", frontend="antlr")
    typed = OfficialSemanticAnalyzer(_resolver).analyze(ast)
    return lower_official_ast(typed, strict=True)


@pytest.mark.parametrize(
    "source,root_kind",
    [
        ("indicator('', '', '涨幅', '', '', '', '') > 5", "LogicalFilter"),
        ("indicator('', '', '涨幅', '', '', '', '') between [1, 5]", "LogicalFilter"),
        ("indicator('', '', '涨幅', '', '', '', '') > 5 limit 0,20", "LogicalLimit"),
        ("rank('', '', '涨幅', 'desc', '', '', '', '') <= 10", "LogicalRank"),
        ("indicator('', '', '成交量', '', '', '', '') > 0 then rank('', '', '涨幅', 'desc', '', '', '', '') <= 10", "LogicalStage"),
    ],
)
def test_supported_queries_lower_to_valid_deterministic_plan(source, root_kind):
    result = _lower(source)

    assert result.plan.to_dict()["kind"] == root_kind
    assert result.plan.node_id == _lower(source).plan.node_id
    assert result.validation_passed is True


def test_unknown_indicator_cannot_enter_strict_logical_plan():
    ast = parse_official_slot("indicator('', '', '未知', '', '', '', '') > 1", mode="strict")
    typed = OfficialSemanticAnalyzer(_resolver).analyze(ast)

    with pytest.raises(OfficialLoweringError) as excinfo:
        lower_official_ast(typed, strict=True)
    assert excinfo.value.code == "UNSUPPORTED_LOGICAL_LOWERING"


def test_rank_lowering_preserves_comparison_contract():
    upper = _lower("rank('', '', '涨幅', 'desc', '', '', '', '') <= 10").plan
    lower = _lower("rank('', '', '涨幅', 'desc', '', '', '', '') >= 10").plan

    assert upper.comparator == "<="
    assert lower.comparator == ">="
    assert upper.node_id != lower.node_id


def test_rank_equality_is_a_relational_filter_contract():
    plan = _lower("rank('', '', '成交量', 'desc', '今日', '', '', '') = 1").plan

    assert plan.to_dict()["kind"] == "LogicalRank"
    assert plan.comparator == "="


def test_rank_greater_than_zero_is_a_valid_relational_contract():
    plan = _lower("rank('', '', '成交量', 'desc', '今日', '', '', '') > 0").plan

    assert plan.to_dict()["kind"] == "LogicalRank"
    assert plan.bound.value == 0


def test_rank_and_scalar_boolean_lower_to_independent_set_intersection():
    plan = _lower(
        "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10 and "
        "indicator('', '', '涨幅', '今日', '', '', '') > 2%"
    ).plan

    assert plan.to_dict()["kind"] == "LogicalSetOperation"
    assert plan.operation == "intersect"
    assert plan.left.to_dict()["kind"] == "LogicalRank"
    assert plan.right.to_dict()["kind"] == "LogicalFilter"


def test_parenthesized_stage_branches_lower_before_set_union():
    plan = _lower(
        "(indicator('', '', '成交量', '', '', '', '') > 0 then "
        "rank('', '', '成交量', 'desc', '', '', '', '') = 1) or "
        "(indicator('', '', '成交量', '', '', '', '') < 0 then "
        "rank('', '', '成交量', 'asc', '', '', '', '') = 1)"
    ).plan

    assert plan.to_dict()["kind"] == "LogicalSetOperation"
    assert plan.operation == "union"
    assert plan.left.to_dict()["kind"] == "LogicalStage"
    assert plan.right.to_dict()["kind"] == "LogicalStage"
