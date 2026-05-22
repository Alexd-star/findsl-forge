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

