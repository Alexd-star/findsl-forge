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


def test_rank_bottom_requires_ascending_order():
    analyzer = SemanticAnalyzer(default_registry())
    with pytest.raises(SemanticError, match="bottom must use asc"):
        analyzer.validate(parse('rank(indicator("close"), desc, bottom=2)'))
