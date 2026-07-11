from __future__ import annotations

from typing import Set

from ..types import BOOLEAN, NUMERIC, UNKNOWN
from .expressions import BinaryExpr, CallExpr, ComparisonExpr, FieldRef, LiteralExpr, LogicalExpr, RangeExpr
from .relational import (
    LogicalAggregate,
    LogicalFilter,
    LogicalDomainScan,
    LogicalEmpty,
    LogicalConsecutive,
    LogicalConstraint,
    LogicalDomainRank,
    LogicalExist,
    LogicalLimit,
    LogicalPlan,
    LogicalProject,
    LogicalRank,
    LogicalScan,
    LogicalStage,
    LogicalWindow,
)


class OfficialIrError(ValueError):
    def __init__(self, code: str, message: str, path: str):
        super().__init__(message)
        self.code = code
        self.path = path


def validate_plan(plan: LogicalPlan, *, strict: bool = True) -> LogicalPlan:
    _validate_plan(plan, "$", strict, set())
    return plan


def _fail(code: str, message: str, path: str) -> None:
    raise OfficialIrError(code, message, path)


def _validate_plan(plan: LogicalPlan, path: str, strict: bool, active: Set[int]) -> None:
    if id(plan) in active:
        _fail("IR_CYCLE", "logical plan contains a cycle", path)
    active.add(id(plan))
    names = [field.name for field in plan.schema.fields]
    if len(names) != len(set(names)):
        _fail("IR_DUPLICATE_FIELD", "logical schema contains duplicate names", f"{path}.schema")
    if isinstance(plan, (LogicalScan, LogicalDomainScan)):
        if "." in plan.entity or plan.entity.lower().startswith("newzl"):
            _fail("IR_PHYSICAL_ENTITY", "logical scan must not name a physical table", f"{path}.entity")
    elif isinstance(plan, LogicalEmpty):
        if not plan.reason.startswith("PROVEN_"):
            _fail("IR_EMPTY_REASON", "empty relation requires a proven logical reason", f"{path}.reason")
    else:
        _validate_plan(plan.input, f"{path}.input", strict, active)
    if isinstance(plan, LogicalFilter):
        if plan.predicate.type is not BOOLEAN:
            if strict and plan.predicate.type is UNKNOWN:
                _fail("IR_UNKNOWN_TYPE", "strict plan contains unknown predicate type", f"{path}.predicate")
            _fail("IR_FILTER_TYPE", "filter predicate must be boolean", f"{path}.predicate")
        _validate_expr(plan.predicate, f"{path}.predicate", strict, names)
    elif isinstance(plan, LogicalLimit):
        if plan.offset < 0 or plan.count <= 0:
            _fail("IR_LIMIT_BOUNDS", "limit offset must be non-negative and count positive", path)
    elif isinstance(plan, LogicalConsecutive):
        if plan.spec.count <= 0:
            _fail("IR_CONSECUTIVE_COUNT", "consecutive count must be positive", f"{path}.spec.count")
    elif isinstance(plan, LogicalExist):
        if plan.spec.minimum < 0 or (plan.spec.maximum is not None and plan.spec.maximum < plan.spec.minimum):
            _fail("IR_EXIST_BOUNDS", "exist bounds are invalid", f"{path}.spec")
    elif isinstance(plan, LogicalDomainRank):
        if plan.spec.direction not in {"asc", "desc"}:
            _fail("IR_RANK_DIRECTION", "domain rank direction must be asc or desc", f"{path}.spec.direction")
    elif isinstance(plan, LogicalConstraint):
        if not plan.market_scope.markets:
            _fail("IR_MARKET_SCOPE", "market scope cannot be empty", f"{path}.market_scope")
    elif isinstance(plan, LogicalRank):
        if plan.direction not in {"asc", "desc"}:
            _fail("IR_RANK_DIRECTION", "rank direction must be asc or desc", f"{path}.direction")
        if not _positive_bound(plan.bound):
            _fail("IR_RANK_BOUND", "rank bound must be a positive numeric or percentage literal", f"{path}.bound")
        _validate_expr(plan.order_by, f"{path}.order_by", strict, names)
    elif isinstance(plan, LogicalStage):
        if plan.stage_index < 1:
            _fail("IR_STAGE_INDEX", "stage index must be positive", f"{path}.stage_index")
        _validate_plan(plan.operation, f"{path}.operation", strict, active)
    elif isinstance(plan, (LogicalProject, LogicalWindow)):
        for index, (_, expression) in enumerate(plan.expressions):
            _validate_expr(expression, f"{path}.expressions[{index}]", strict, names)
    elif isinstance(plan, LogicalAggregate):
        for index, expression in enumerate(plan.group_keys):
            _validate_expr(expression, f"{path}.group_keys[{index}]", strict, names)
        for index, (_, expression) in enumerate(plan.measures):
            _validate_expr(expression, f"{path}.measures[{index}]", strict, names)
    active.remove(id(plan))


def _positive_bound(expression: LogicalExpr) -> bool:
    if not isinstance(expression, LiteralExpr):
        return False
    if isinstance(expression.value, (int, float)) and not isinstance(expression.value, bool):
        return expression.value > 0
    if isinstance(expression.value, str) and expression.value.endswith("%"):
        try:
            return float(expression.value[:-1]) > 0
        except ValueError:
            return False
    return False


def _validate_expr(expression: LogicalExpr, path: str, strict: bool, fields) -> None:
    if strict and expression.type is UNKNOWN:
        _fail("IR_UNKNOWN_TYPE", "strict plan contains unknown expression type", path)
    if isinstance(expression, FieldRef) and expression.name not in fields:
        _fail("IR_UNBOUND_FIELD", f"field {expression.name} is not in input schema", path)
    if isinstance(expression, (BinaryExpr, ComparisonExpr)):
        _validate_expr(expression.left, f"{path}.left", strict, fields)
        _validate_expr(expression.right, f"{path}.right", strict, fields)
    elif isinstance(expression, CallExpr):
        for index, arg in enumerate(expression.args):
            _validate_expr(arg, f"{path}.args[{index}]", strict, fields)
    elif isinstance(expression, RangeExpr):
        _validate_expr(expression.lower, f"{path}.lower", strict, fields)
        _validate_expr(expression.upper, f"{path}.upper", strict, fields)
