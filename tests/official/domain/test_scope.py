import pytest

from findsl.official.domain.scope import (
    ScopeAnd,
    ScopeAtom,
    ScopeNot,
    ScopeOr,
    ScopeParseError,
    parse_scope_expression,
)


def test_scope_parser_uses_not_then_intersection_then_union_precedence():
    expression = parse_scope_expression("华泰证券|中科曙光&^农业银行")

    assert isinstance(expression, ScopeOr)
    assert expression.left == ScopeAtom("华泰证券")
    assert isinstance(expression.right, ScopeAnd)
    assert expression.right.left == ScopeAtom("中科曙光")
    assert expression.right.right == ScopeNot(ScopeAtom("农业银行"))


@pytest.mark.parametrize("source", ["华泰证券||农业银行", "华泰证券&&农业银行", "华泰证券|", "&华泰证券", "^^"])
def test_invalid_scope_expression_has_stable_diagnostic(source):
    with pytest.raises(ScopeParseError) as excinfo:
        parse_scope_expression(source)

    assert excinfo.value.code == "SCOPE_EXPRESSION_INVALID"


def test_empty_scope_has_no_constraint():
    assert parse_scope_expression("") is None
