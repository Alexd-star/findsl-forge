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
