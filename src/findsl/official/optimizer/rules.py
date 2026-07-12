from __future__ import annotations

import operator
from dataclasses import replace

from ..ir import BinaryExpr, ComparisonExpr, LiteralExpr, LogicalConstraint, LogicalEmpty, LogicalFilter, LogicalLimit, LogicalRank
from ..ir.expressions import CallExpr, LogicalExpr, RangeExpr
from ..ir.relational import LogicalPlan, LogicalSetOperation, LogicalStage
from ..types import BOOLEAN


def _rewrite_inputs(plan: LogicalPlan, callback):
    result = plan
    if isinstance(plan, LogicalSetOperation):
        return replace(
            result,
            left=callback(plan.left),
            right=callback(plan.right),
        )
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


class BoolFlattenRule:
    rule_id = "BOOL_FLATTEN"
    version = "1"
    proof_obligation = "Associativity permits canonical regrouping without reordering operands."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalFilter):
            return replace(plan, predicate=self._normalize(plan.predicate))
        return plan

    def _normalize(self, expression):
        expression = _rewrite_expr(expression, self._normalize)
        if not isinstance(expression, BinaryExpr) or expression.op not in {"and", "or"}:
            return expression
        operands = []
        def collect(value):
            if isinstance(value, BinaryExpr) and value.op == expression.op:
                collect(value.left)
                collect(value.right)
            else:
                operands.append(value)
        collect(expression)
        result = operands[0]
        for operand in operands[1:]:
            result = BinaryExpr(expression.op, result, operand, expression.type)
        return result


class ConstraintMergeRule:
    rule_id = "CONSTRAINT_MERGE"
    version = "1"
    proof_obligation = "Intersection of explicit market sets and exact/unspecified dates preserves conjunction semantics."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if not isinstance(plan, LogicalConstraint) or not isinstance(plan.input, LogicalConstraint):
            return plan
        inner = plan.input
        left = set(inner.market_scope.markets)
        right = set(plan.market_scope.markets)
        markets = left if right == {"ALL"} else right if left == {"ALL"} else left & right
        if not markets:
            return LogicalEmpty(plan.schema, "PROVEN_MARKET_INTERSECTION_EMPTY")
        first, second = inner.date_constraint, plan.date_constraint
        if first.kind == "unspecified":
            date = second
        elif second.kind == "unspecified":
            date = first
        elif first.to_dict() == second.to_dict():
            date = first
        elif first.kind == second.kind == "exact":
            return LogicalEmpty(plan.schema, "PROVEN_DATE_INTERSECTION_EMPTY")
        else:
            return plan
        from ..domain import MarketScope
        return LogicalConstraint(inner.input, MarketScope(tuple(sorted(markets))), date, plan.schema)


class FilterPushDownRule:
    rule_id = "FILTER_PUSH_DOWN"
    version = "1"
    proof_obligation = "A row-local predicate commutes with declarative market/date restriction."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalFilter) and isinstance(plan.input, LogicalConstraint) and self._row_local(plan.predicate):
            constraint = plan.input
            pushed = LogicalFilter(constraint.input, plan.predicate, plan.schema)
            return LogicalConstraint(pushed, constraint.market_scope, constraint.date_constraint, plan.schema)
        return plan

    def _row_local(self, expression):
        if isinstance(expression, (LiteralExpr,)):
            return True
        from ..ir import FieldRef
        if isinstance(expression, FieldRef):
            return True
        if isinstance(expression, (BinaryExpr, ComparisonExpr)):
            return self._row_local(expression.left) and self._row_local(expression.right)
        return False


class StageNormalizeRule:
    rule_id = "STAGE_NORMALIZE"
    version = "1"
    proof_obligation = "Stage indexes are metadata and may be renumbered without changing operations."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalStage):
            expected = plan.input.stage_index + 1 if isinstance(plan.input, LogicalStage) else 1
            return replace(plan, stage_index=expected)
        return plan


class RankContractNormalizeRule:
    rule_id = "RANK_CONTRACT_NORMALIZE"
    version = "1"
    proof_obligation = "Case normalization and removal of unary plus preserve rank direction and bound."

    def apply(self, plan):
        plan = _rewrite_inputs(plan, self.apply)
        if isinstance(plan, LogicalRank):
            direction = plan.direction.lower()
            bound = plan.bound
            upper_bound = plan.upper_bound
            if isinstance(bound, LiteralExpr) and isinstance(bound.value, str) and bound.value.startswith("+"):
                bound = replace(bound, value=bound.value[1:])
            if (
                isinstance(upper_bound, LiteralExpr)
                and isinstance(upper_bound.value, str)
                and upper_bound.value.startswith("+")
            ):
                upper_bound = replace(upper_bound, value=upper_bound.value[1:])
            return replace(
                plan,
                direction=direction,
                bound=bound,
                upper_bound=upper_bound,
            )
        return plan
