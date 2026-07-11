from __future__ import annotations

import operator
from dataclasses import replace

from ..ir import BinaryExpr, ComparisonExpr, LiteralExpr, LogicalEmpty, LogicalFilter, LogicalLimit
from ..ir.expressions import CallExpr, LogicalExpr, RangeExpr
from ..ir.relational import LogicalPlan, LogicalStage
from ..types import BOOLEAN, NUMERIC


def _rewrite_inputs(plan: LogicalPlan, callback):
    result = plan
    if hasattr(plan, "input"):
        result = replace(result, input=callback(plan.input))
    if isinstance(result, LogicalStage):
        result = replace(result, operation=callback(result.operation))
    return result


def _rewrite_expr(expression: LogicalExpr, callback):
    value = expression
    if isinstance(expression, (BinaryExpr, ComparisonExpr)):
        value = replace(expression, left=callback(expression.left), right=callback(expression.right))
    elif isinstance(expression, CallExpr):
        value = replace(expression, args=tuple(callback(arg) for arg in expression.args))
    elif isinstance(expression, RangeExpr):
        value = replace(expression, lower=callback(expression.lower), upper=callback(expression.upper))
    return value


class ConstFoldRule:
    rule_id = "CONST_FOLD"
    version = "1"
    proof_obligation = "Only pure literal expressions are evaluated with the same typed operator."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalFilter):
            return replace(plan, predicate=self._fold(plan.predicate))
        return plan

    def _fold(self, expression):
        expression = _rewrite_expr(expression, self._fold)
        if isinstance(expression, BinaryExpr) and isinstance(expression.left, LiteralExpr) and isinstance(expression.right, LiteralExpr):
            operations = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv, "and": lambda a, b: bool(a and b), "or": lambda a, b: bool(a or b)}
            if expression.op in operations and not (expression.op == "/" and expression.right.value == 0):
                return LiteralExpr(operations[expression.op](expression.left.value, expression.right.value), expression.type)
        if isinstance(expression, ComparisonExpr) and isinstance(expression.left, LiteralExpr) and isinstance(expression.right, LiteralExpr):
            operations = {"=": operator.eq, "!=": operator.ne, ">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}
            if expression.op in operations:
                return LiteralExpr(operations[expression.op](expression.left.value, expression.right.value), BOOLEAN)
        return expression


class PredicateDedupRule:
    rule_id = "PREDICATE_DEDUP"
    version = "1"
    proof_obligation = "Idempotence of boolean AND/OR permits removal of identical operands."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalFilter):
            return replace(plan, predicate=self._dedup(plan.predicate))
        return plan

    def _dedup(self, expression):
        expression = _rewrite_expr(expression, self._dedup)
        if isinstance(expression, BinaryExpr) and expression.op in {"and", "or"} and expression.left.node_id == expression.right.node_id:
            return expression.left
        return expression


class FilterMergeRule:
    rule_id = "FILTER_MERGE"
    version = "1"
    proof_obligation = "Two adjacent filters equal one filter with conjunction when no semantic barrier intervenes."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalFilter) and isinstance(plan.input, LogicalFilter):
            inner = plan.input
            predicate = BinaryExpr("and", inner.predicate, plan.predicate, BOOLEAN)
            return LogicalFilter(inner.input, predicate, plan.schema)
        return plan


class LimitNormalizeRule:
    rule_id = "LIMIT_NORMALIZE"
    version = "1"
    proof_obligation = "Nested relational slices compose by adding offsets and intersecting available counts."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalLimit) and isinstance(plan.input, LogicalLimit):
            inner = plan.input
            available = max(0, inner.count - plan.offset)
            if available == 0:
                return LogicalEmpty(plan.schema, "PROVEN_LIMIT_INTERSECTION_EMPTY")
            return LogicalLimit(inner.input, inner.offset + plan.offset, min(plan.count, available), plan.schema)
        return plan
