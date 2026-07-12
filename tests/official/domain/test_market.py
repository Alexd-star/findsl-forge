import pytest

from findsl.official.domain.market import (
    MarketAnd,
    MarketAtom,
    MarketNot,
    MarketOr,
    MarketParseError,
    parse_market_expression,
)


def test_market_parser_uses_not_then_intersection_then_union_precedence():
    expression = parse_market_expression("沪|深&^创业板")

    assert isinstance(expression, MarketOr)
    assert expression.left == MarketAtom("沪")
    assert isinstance(expression.right, MarketAnd)
    assert expression.right.left == MarketAtom("深")
    assert expression.right.right == MarketNot(MarketAtom("创业板"))


@pytest.mark.parametrize(
    "source",
    ["沪||深", "沪&&深", "沪|", "&沪", "^^", "未知市场"],
)
def test_invalid_market_expression_has_stable_diagnostic(source):
    with pytest.raises(MarketParseError) as excinfo:
        parse_market_expression(source)

    assert excinfo.value.code in {
        "MARKET_EXPRESSION_INVALID",
        "MARKET_TOKEN_UNSUPPORTED",
    }


def test_official_but_unavailable_market_is_preserved_for_physical_diagnostic():
    assert parse_market_expression("港") == MarketAtom("港")
