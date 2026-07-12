from __future__ import annotations

import operator
from typing import Any, Iterable, Mapping, Tuple

from ..ir import BinaryExpr, ComparisonExpr, FieldRef, LiteralExpr, LogicalDomainScan, LogicalEmpty, LogicalFilter, LogicalLimit, LogicalScan


def interpret(plan, rows: Iterable[Mapping[str, Any]]) -> Tuple[Mapping[str, Any], ...]:
    source = tuple(rows)
    if isinstance(plan, (LogicalScan, LogicalDomainScan)):
        return source
    if isinstance(plan, LogicalEmpty):
        return ()
    if isinstance(plan, LogicalFilter):
        values = interpret(plan.input, source)
        return tuple(row for row in values if bool(_evaluate(plan.predicate, row)))
    if isinstance(plan, LogicalLimit):
        values = interpret(plan.input, source)
        stop = None if plan.count is None else plan.offset + plan.count
        return values[plan.offset:stop]
    raise ValueError(f"interpreter does not support {type(plan).__name__}")


def _evaluate(expression, row):
    if isinstance(expression, LiteralExpr):
        return expression.value
    if isinstance(expression, FieldRef):
        return row[expression.name]
    if isinstance(expression, BinaryExpr):
        left, right = _evaluate(expression.left, row), _evaluate(expression.right, row)
        operations = {"and": lambda a, b: bool(a and b), "or": lambda a, b: bool(a or b), "+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
        return operations[expression.op](left, right)
    if isinstance(expression, ComparisonExpr):
        left, right = _evaluate(expression.left, row), _evaluate(expression.right, row)
        operations = {"=": operator.eq, "!=": operator.ne, ">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}
        return operations[expression.op](left, right)
    raise ValueError(f"interpreter does not support {type(expression).__name__}")
