import pytest

from findsl.official.domain import ConsecutiveSpec, EventSpec, IndicatorRef
from findsl.official.ir import LogicalConsecutive
from findsl.official.lowering import OfficialLoweringError, lower_official_ast
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot


def _typed(source):
    return OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parse_official_slot(source, mode="strict"))


def test_domain_lowering_attaches_requirement_and_indicator_binding():
    result = lower_official_ast(
        _typed("indicator('', '', '涨幅', '今日', '', '', '') > 5"),
        domain_registry=default_official_registry(),
    )

    assert result.plan.to_dict()["input"]["kind"] == "LogicalDomainScan"
    assert result.domain_bindings[0].requirement.domains == frozenset({"quote"})
    assert isinstance(result.domain_bindings[0].expression, IndicatorRef)


def test_domain_lowering_promotes_cross_to_event_expression():
    result = lower_official_ast(
        _typed("cross_above('', '', '涨幅', '成交量', '今日', '', '') = True"),
        domain_registry=default_official_registry(),
    )
    assert isinstance(result.domain_bindings[0].expression, EventSpec)


def test_domain_lowering_preserves_precise_unknown_indicator_code():
    with pytest.raises(OfficialLoweringError) as excinfo:
        lower_official_ast(
            _typed("indicator('', '', '不存在指标', '今日', '', '', '') > 1"),
            domain_registry=default_official_registry(),
        )
    assert excinfo.value.code == "DOMAIN_UNKNOWN_INDICATOR"


def test_domain_lowering_materializes_count_expression_as_logical_temporal_plan():
    result = lower_official_ast(
        _typed("indicator('', '', '涨幅', '最近10日', '', '', 'CONS=3日') > 0"),
        domain_registry=default_official_registry(),
    )

    assert isinstance(result.plan, LogicalConsecutive)
    assert isinstance(result.plan.spec, ConsecutiveSpec)
    assert result.plan.spec.threshold == 3
    assert result.plan.spec.unit == "日"
    assert result.plan.spec.predicate.to_dict()["kind"] == "ComparisonExpr"
