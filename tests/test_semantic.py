import pytest

from findsl.errors import SemanticError
from findsl.parser import parse
from findsl.registry import default_registry
from findsl.semantic import SemanticAnalyzer


def test_unknown_indicator_is_rejected():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(Exception):
        analyzer.validate(parse('filter(indicator("not_exists") > 0)'))


def test_cons_requires_boolean_condition():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError):
        analyzer.validate(parse('filter(CONS(indicator("close"), 3))'))


def test_date_between_rejects_reversed_range():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="start date"):
        analyzer.validate(parse('filter(date_between("2026-01-04", "2026-01-02"))'))


def test_date_between_rejects_non_iso_date_strings():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="ISO date"):
        analyzer.validate(parse('filter(date_between("2026/01/01", "2026-01-02"))'))


def test_rank_bottom_requires_ascending_order():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="bottom must use asc"):
        analyzer.validate(parse('rank(indicator("close"), desc, bottom=2)'))


def test_bare_identifier_comparison_is_rejected():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match='indicator\\("close"\\)'):
        analyzer.validate(parse("close > 10"))


def test_filter_bare_identifier_single_equal_named_arg_is_rejected_with_context():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="filter does not allow named arg close"):
        analyzer.validate(parse("filter(close=10)"))


def test_filter_requires_boolean_condition_in_semantic_layer():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="filter\\(\\) condition must be boolean"):
        analyzer.validate(parse('filter(indicator("close"))'))


def test_then_stage_must_be_relation_producing_filter_or_rank():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="then\\(\\) stages must be relation-producing"):
        analyzer.validate(parse('then(filter(indicator("close") > 10), indicator("volume"))'))


def test_window_argument_must_be_integer_literal_in_semantic_layer():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="MA window must be an integer literal"):
        analyzer.validate(parse('filter(MA(indicator("close"), 2.5) > 10)'))


def test_market_argument_must_be_symbolic_in_semantic_layer():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="market\\(\\) requires a string or identifier argument"):
        analyzer.validate(parse("filter(market(1))"))


def test_indicator_argument_must_be_symbolic_in_semantic_layer():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="indicator\\(\\) requires a string or identifier argument"):
        analyzer.validate(parse("filter(indicator(123) > 10)"))


def test_literal_division_by_zero_is_rejected_in_semantic_layer():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="Division by zero"):
        analyzer.validate(parse('filter((indicator("close") / 0) > 1)'))
