from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..ir import (
    BinaryExpr,
    CallExpr,
    ComparisonExpr,
    LiteralExpr,
    LogicalDomainScan,
    LogicalFilter,
    LogicalLimit,
)
from ..lowering import LoweringResult
from ..types import BOOLEAN, NUMERIC, STRING, TIME, OfficialType
from .catalog import PhysicalCatalog, PhysicalField
from .ir import (
    PhysicalBinary,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalFilter,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalPlan,
    PhysicalScan,
)
from .validate import validate_physical_plan


@dataclass(frozen=True)
class PhysicalDecision:
    resource_id: Optional[str]
    feasible: bool
    cost: Optional[float]
    estimated: bool
    reason_code: str
    reason: str


class PhysicalPlanningError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        decisions: Tuple[PhysicalDecision, ...] = (),
    ):
        super().__init__(message)
        self.code = code
        self.decisions = decisions


@dataclass(frozen=True)
class PhysicalPlanningResult:
    plan: PhysicalPlan
    selected_resource: str
    decisions: Tuple[PhysicalDecision, ...]


_TYPE_MAP = {
    "boolean": BOOLEAN,
    "numeric": NUMERIC,
    "string": STRING,
    "time": TIME,
}


def plan_physical(lowering: LoweringResult, catalog: PhysicalCatalog) -> PhysicalPlanningResult:
    fields = _collect_fields(lowering.plan, catalog)
    resource_ids = tuple(sorted({field.resource_id for field in fields}))
    if not resource_ids:
        raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", "logical plan has no directly mapped physical indicator")
    if len(resource_ids) != 1:
        raise PhysicalPlanningError("PHYSICAL_MULTI_RESOURCE_UNSUPPORTED", "bounded planner currently requires one physical resource")

    selected = resource_ids[0]
    resource = catalog.resource(selected)
    plan = _lower_plan(lowering.plan, catalog, selected, fields)
    validate_physical_plan(plan, catalog)
    decision = PhysicalDecision(
        resource_id=selected,
        feasible=True,
        cost=float(resource.priority),
        estimated=True,
        reason_code="PHYSICAL_CANDIDATE_SELECTED",
        reason="catalog priority used because runtime statistics are unavailable",
    )
    return PhysicalPlanningResult(plan, selected, (decision,))


def _collect_fields(plan, catalog: PhysicalCatalog) -> Tuple[PhysicalField, ...]:
    expressions = []
    current = plan
    while isinstance(current, (LogicalFilter, LogicalLimit)):
        if isinstance(current, LogicalFilter):
            expressions.append(current.predicate)
        current = current.input
    if not isinstance(current, LogicalDomainScan):
        raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical root {type(current).__name__}")

    fields = []
    for expression in expressions:
        for call in _walk_calls(expression):
            if call.name != "indicator" or call.binding is None:
                raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {call.name}")
            indicator_id = call.binding.slots.get("indicator_name", "")
            try:
                fields.append(catalog.indicator(indicator_id))
            except KeyError as exc:
                decision = PhysicalDecision(
                    resource_id=None,
                    feasible=False,
                    cost=None,
                    estimated=False,
                    reason_code="PHYSICAL_MAPPING_MISSING",
                    reason=f"no controlled physical mapping for indicator {indicator_id}",
                )
                raise PhysicalPlanningError(
                    "PHYSICAL_PLAN_UNAVAILABLE",
                    f"no controlled physical mapping for indicator {indicator_id}",
                    decisions=(decision,),
                ) from exc
    return tuple(fields)


def _walk_calls(expression):
    if isinstance(expression, CallExpr):
        yield expression
        for argument in expression.args:
            yield from _walk_calls(argument)
    elif isinstance(expression, (BinaryExpr, ComparisonExpr)):
        yield from _walk_calls(expression.left)
        yield from _walk_calls(expression.right)


def _lower_plan(plan, catalog: PhysicalCatalog, resource_id: str, fields: Tuple[PhysicalField, ...]) -> PhysicalPlan:
    if isinstance(plan, LogicalDomainScan):
        columns = tuple(
            PhysicalColumn(field.resource_id, field.column, _physical_type(field))
            for field in _deduplicate_fields(fields)
        )
        return PhysicalScan(resource_id, columns, None)
    if isinstance(plan, LogicalFilter):
        return PhysicalFilter(
            _lower_plan(plan.input, catalog, resource_id, fields),
            _lower_expr(plan.predicate, catalog, resource_id),
        )
    if isinstance(plan, LogicalLimit):
        return PhysicalLimit(
            _lower_plan(plan.input, catalog, resource_id, fields),
            plan.offset,
            plan.count,
        )
    raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical node {type(plan).__name__}")


def _lower_expr(expression, catalog: PhysicalCatalog, resource_id: str):
    if isinstance(expression, LiteralExpr):
        return PhysicalLiteral(expression.value, expression.type)
    if isinstance(expression, CallExpr):
        if expression.name != "indicator" or expression.binding is None:
            raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {expression.name}")
        indicator_id = expression.binding.slots.get("indicator_name", "")
        try:
            field = catalog.indicator(indicator_id)
        except KeyError as exc:
            raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", f"no controlled physical mapping for indicator {indicator_id}") from exc
        if field.resource_id != resource_id:
            raise PhysicalPlanningError("PHYSICAL_MULTI_RESOURCE_UNSUPPORTED", "expression spans multiple physical resources")
        return PhysicalColumn(field.resource_id, field.column, _physical_type(field))
    if isinstance(expression, BinaryExpr):
        return PhysicalBinary(
            expression.op,
            _lower_expr(expression.left, catalog, resource_id),
            _lower_expr(expression.right, catalog, resource_id),
            expression.type,
        )
    if isinstance(expression, ComparisonExpr):
        return PhysicalComparison(
            expression.op,
            _lower_expr(expression.left, catalog, resource_id),
            _lower_expr(expression.right, catalog, resource_id),
        )
    raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported expression {type(expression).__name__}")


def _physical_type(field: PhysicalField) -> OfficialType:
    try:
        return _TYPE_MAP[field.value_type]
    except KeyError as exc:
        raise PhysicalPlanningError("PHYSICAL_TYPE_UNSUPPORTED", f"unsupported physical type {field.value_type}") from exc


def _deduplicate_fields(fields: Tuple[PhysicalField, ...]) -> Tuple[PhysicalField, ...]:
    unique = {}
    for field in fields:
        unique[(field.resource_id, field.column)] = field
    return tuple(unique[key] for key in sorted(unique))
