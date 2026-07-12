from __future__ import annotations

from typing import Optional, Set

from ..types import BOOLEAN, UNKNOWN
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
    LogicalSetOperation,
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
    elif isinstance(plan, LogicalSetOperation):
        if plan.operation not in {"intersect", "union"}:
            _fail("IR_SET_OPERATION", "logical set operation is unsupported", f"{path}.operation")
        if plan.left.schema.to_dict() != plan.right.schema.to_dict() or plan.schema.to_dict() != plan.left.schema.to_dict():
            _fail("IR_SET_SCHEMA", "set-operation branch schemas must match", f"{path}.schema")
        _validate_plan(plan.left, f"{path}.left", strict, active)
        _validate_plan(plan.right, f"{path}.right", strict, active)
    else:
        _validate_plan(plan.input, f"{path}.input", strict, active)
    if isinstance(plan, LogicalFilter):
        if plan.predicate.type is not BOOLEAN:
            if strict and plan.predicate.type is UNKNOWN:
                _fail("IR_UNKNOWN_TYPE", "strict plan contains unknown predicate type", f"{path}.predicate")
            _fail("IR_FILTER_TYPE", "filter predicate must be boolean", f"{path}.predicate")
        _validate_expr(plan.predicate, f"{path}.predicate", strict, names)
    elif isinstance(plan, LogicalLimit):
        if plan.offset < 0 or (plan.count is not None and plan.count <= 0):
            _fail("IR_LIMIT_BOUNDS", "limit offset must be non-negative and count positive", path)
    elif isinstance(plan, LogicalConsecutive):
        _validate_temporal_spec(plan.spec, path, "CONS")
    elif isinstance(plan, LogicalExist):
        _validate_temporal_spec(plan.spec, path, "EXIST")
    elif isinstance(plan, LogicalDomainRank):
        if plan.spec.direction not in {"asc", "desc"}:
            _fail("IR_RANK_DIRECTION", "domain rank direction must be asc or desc", f"{path}.spec.direction")
    elif isinstance(plan, LogicalConstraint):
        if not plan.market_scope.markets:
            _fail("IR_MARKET_SCOPE", "market scope cannot be empty", f"{path}.market_scope")
    elif isinstance(plan, LogicalRank):
        if plan.direction not in {"asc", "desc"}:
            _fail("IR_RANK_DIRECTION", "rank direction must be asc or desc", f"{path}.direction")
        if plan.comparator not in {"<", "<=", "=", "!=", ">", ">=", "between"}:
            _fail("IR_RANK_COMPARATOR", "rank comparator is unsupported", f"{path}.comparator")
        if plan.comparator == "between":
            lower = _rank_bound_value(plan.bound)
            upper = _rank_bound_value(plan.upper_bound)
            if (
                lower is None
                or upper is None
                or lower[1] != upper[1]
                or lower[0] < 0
                or upper[0] < lower[0]
                or (lower[1] and upper[0] > 100)
            ):
                _fail("IR_RANK_BOUND", "rank range is invalid", f"{path}.bound")
        else:
            if plan.upper_bound is not None:
                _fail("IR_RANK_BOUND", "scalar rank cannot carry an upper bound", f"{path}.upper_bound")
            if not _valid_rank_bound(plan.bound, plan.comparator):
                _fail("IR_RANK_BOUND", "rank bound is invalid for its comparator", f"{path}.bound")
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


def _validate_temporal_spec(spec, path: str, mode: str) -> None:
    if spec.comparator not in {"<", "<=", "=", "!=", ">", ">=", "between"}:
        _fail("IR_TEMPORAL_COMPARATOR", "temporal comparator is unsupported", f"{path}.spec.comparator")
    if not spec.trading_sequence:
        _fail("IR_TEMPORAL_SEQUENCE", "official temporal semantics require trading sequence order", f"{path}.spec")
    if spec.every:
        if (
            spec.threshold is not None
            or spec.maximum is not None
            or not spec.unit
            or spec.comparator not in {"=", "!="}
        ):
            _fail("IR_TEMPORAL_EVERY", "invalid every-bucket temporal contract", f"{path}.spec")
    else:
        if spec.threshold is None or spec.threshold < 0:
            _fail("IR_TEMPORAL_THRESHOLD", "temporal threshold is invalid", f"{path}.spec.threshold")
        if mode == "CONS" and spec.threshold <= 0:
            _fail("IR_CONSECUTIVE_COUNT", "consecutive count must be positive", f"{path}.spec.threshold")
        if spec.maximum is not None and spec.maximum < spec.threshold:
            _fail("IR_TEMPORAL_RANGE", "temporal range is invalid", f"{path}.spec")
    _validate_expr(spec.predicate, f"{path}.spec.predicate", True, [])


def _valid_rank_bound(expression: LogicalExpr, comparator: str) -> bool:
    parsed = _rank_bound_value(expression)
    if parsed is None:
        return False
    value, percentage = parsed
    if percentage and value > 100:
        return False
    return value > 0 or (value == 0 and comparator in {">", ">="})


def _rank_bound_value(expression: Optional[LogicalExpr]):
    if not isinstance(expression, LiteralExpr):
        return None
    if isinstance(expression.value, (int, float)) and not isinstance(
        expression.value, bool
    ):
        return float(expression.value), False
    if isinstance(expression.value, str) and expression.value.endswith("%"):
        try:
            return float(expression.value[:-1]), True
        except ValueError:
            return None
    return None


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
