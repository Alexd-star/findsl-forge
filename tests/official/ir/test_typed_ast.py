from findsl.official.ast import OfficialFunctionCall, OfficialLiteral
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official.types import BOOLEAN, NUMERIC, UNKNOWN
from findsl.official_slot import IndicatorMeta, parse_official_slot


def _resolve(name):
    return {"涨幅": IndicatorMeta("basic", kind="numeric")}.get(name)


def test_semantic_analysis_returns_typed_tree_with_function_binding():
    ast = parse_official_slot("indicator('', '', '涨幅', '今日', '', '', '') > 5")
    typed = OfficialSemanticAnalyzer(_resolve).analyze(ast)

    assert typed.type is BOOLEAN
    assert typed.children[0].type is NUMERIC
    assert typed.children[0].binding.signature.name == "indicator"
    assert typed.children[0].binding.slots["indicator_name"] == "涨幅"
    assert typed.to_dict()["type"] == {"kind": "boolean"}


def test_unknown_indicator_is_typed_unknown_without_losing_binding():
    call = OfficialFunctionCall(
        "indicator",
        [OfficialLiteral(""), OfficialLiteral(""), OfficialLiteral("未知"), *[OfficialLiteral("")] * 4],
    )
    typed = OfficialSemanticAnalyzer(_resolve).analyze(call)

    assert typed.type is UNKNOWN
    assert typed.binding is not None


def test_validate_remains_legacy_string_compatible():
    ast = parse_official_slot("indicator('', '', '涨幅', '', '', '', '') > 1")
    analyzer = OfficialSemanticAnalyzer(_resolve)

    assert analyzer.validate(ast) == "boolean"
    assert analyzer.analyze(ast).canonical_json() == analyzer.analyze(ast).canonical_json()
