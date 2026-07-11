from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Tuple

from ..ir import (
    BinaryExpr,
    CallExpr,
    ComparisonExpr,
    LiteralExpr,
    LogicalDomainScan,
    LogicalFilter,
    LogicalLimit,
    LogicalRank,
    LogicalStage,
    RangeExpr,
)
from ..lowering import LoweringResult
from ..types import BOOLEAN, NUMERIC, STRING, TIME, OfficialType
from .catalog import PhysicalCatalog, PhysicalField
from .ir import (
    PhysicalBinary,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalFilter,
    PhysicalIn,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalPlan,
    PhysicalRank,
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
_DIRECT_FIELD_CALLS = {"indicator", "queryData", "rank"}


def plan_physical(lowering: LoweringResult, catalog: PhysicalCatalog) -> PhysicalPlanningResult:
    fields = _collect_fields(lowering.plan, catalog)
    resource_ids = tuple(sorted({field.resource_id for field in fields}))
    if not resource_ids:
        raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", "logical plan has no directly mapped physical indicator")
    if len(resource_ids) != 1:
        raise PhysicalPlanningError("PHYSICAL_MULTI_RESOURCE_UNSUPPORTED", "bounded planner currently requires one physical resource")

    selected = resource_ids[0]
    resource = catalog.resource(selected)
    required_keys = {"mktcode", "tgtcode", "bizdate"}
    available_keys = set(resource.stable_keys)
    if resource.anchor_resource_id:
        available_keys.update(catalog.resource(resource.anchor_resource_id).stable_keys)
    if not required_keys.issubset(available_keys):
        raise PhysicalPlanningError(
            "PHYSICAL_STABLE_KEY_UNAVAILABLE",
            f"resource {selected} cannot directly produce stable result keys",
        )
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
    while isinstance(current, (LogicalFilter, LogicalLimit, LogicalRank, LogicalStage)):
        if isinstance(current, LogicalFilter):
            expressions.append(current.predicate)
        elif isinstance(current, LogicalRank):
            expressions.append(current.order_by)
        current = current.operation if isinstance(current, LogicalStage) else current.input
    if not isinstance(current, LogicalDomainScan):
        raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical root {type(current).__name__}")

    fields = []
    for expression in expressions:
        for call in _walk_calls(expression):
            if call.name not in _DIRECT_FIELD_CALLS or call.binding is None:
                raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {call.name}")
            _reject_unmaterialized_constraints(call)
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
    elif isinstance(expression, RangeExpr):
        yield from _walk_calls(expression.lower)
        yield from _walk_calls(expression.upper)


def _reject_unmaterialized_constraints(call: CallExpr) -> None:
    ignored = {
        slot: value
        for slot, value in call.binding.slots.items()
        if slot not in {"indicator_name", "market", "date", "direction"} and str(value).strip()
    }
    if ignored:
        names = ", ".join(sorted(ignored))
        raise PhysicalPlanningError(
            "PHYSICAL_CONSTRAINT_UNSUPPORTED",
            f"physical planner cannot yet materialize non-empty slot(s): {names}",
        )


def _lower_plan(plan, catalog: PhysicalCatalog, resource_id: str, fields: Tuple[PhysicalField, ...]) -> PhysicalPlan:
    if isinstance(plan, LogicalDomainScan):
        columns = tuple(
            PhysicalColumn(field.resource_id, field.column, _physical_type(field))
            for field in _deduplicate_fields(fields)
        )
        resource = catalog.resource(resource_id)
        return PhysicalScan(resource_id, columns, None, resource.anchor_resource_id)
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
    if isinstance(plan, LogicalRank):
        input_plan = _lower_plan(plan.input, catalog, resource_id, fields)
        if isinstance(input_plan, PhysicalRank):
            raise PhysicalPlanningError(
                "PHYSICAL_CHAINED_RANK_UNSUPPORTED",
                "chained rank requires explicit stage-output alias propagation",
            )
        for constraint in _call_constraints(plan.order_by, catalog, resource_id):
            input_plan = PhysicalFilter(input_plan, constraint)
        expression = _lower_expr(plan.order_by, catalog, resource_id, allow_rank=True)
        bound = _lower_expr(plan.bound, catalog, resource_id)
        if not isinstance(bound, PhysicalLiteral) or not isinstance(bound.value, (int, float)):
            raise PhysicalPlanningError("PHYSICAL_RANK_BOUND_UNSUPPORTED", "physical rank requires a numeric literal bound")
        return PhysicalRank(input_plan, expression, plan.direction, bound, plan.comparator)
    if isinstance(plan, LogicalStage):
        return _lower_plan(plan.operation, catalog, resource_id, fields)
    raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical node {type(plan).__name__}")


def _lower_expr(expression, catalog: PhysicalCatalog, resource_id: str, *, allow_rank: bool = False):
    if isinstance(expression, LiteralExpr):
        return PhysicalLiteral(expression.value, expression.type)
    if isinstance(expression, CallExpr):
        if expression.name not in _DIRECT_FIELD_CALLS or expression.binding is None:
            raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {expression.name}")
        if expression.name == "rank" and not allow_rank:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
                "rank inside a scalar expression requires an explicit window plan",
            )
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
            _lower_expr(expression.left, catalog, resource_id, allow_rank=allow_rank),
            _lower_expr(expression.right, catalog, resource_id, allow_rank=allow_rank),
            expression.type,
        )
    if isinstance(expression, ComparisonExpr):
        if expression.op == "~=":
            raise PhysicalPlanningError(
                "PHYSICAL_APPROXIMATION_POLICY_MISSING",
                "approximate comparison requires catalog-provided absolute and relative tolerances",
            )
        if isinstance(expression.right, RangeExpr) and expression.op == "between":
            value = _lower_expr(expression.left, catalog, resource_id, allow_rank=allow_rank)
            lower = _lower_expr(expression.right.lower, catalog, resource_id, allow_rank=allow_rank)
            upper = _lower_expr(expression.right.upper, catalog, resource_id, allow_rank=allow_rank)
            lower_op = ">=" if expression.right.lower_inclusive else ">"
            upper_op = "<=" if expression.right.upper_inclusive else "<"
            result = PhysicalBinary(
                "and",
                PhysicalComparison(lower_op, value, lower),
                PhysicalComparison(upper_op, value, upper),
                BOOLEAN,
            )
        else:
            result = PhysicalComparison(
                expression.op,
                _lower_expr(expression.left, catalog, resource_id, allow_rank=allow_rank),
                _lower_expr(expression.right, catalog, resource_id, allow_rank=allow_rank),
            )
        return _apply_call_constraints(result, expression, catalog, resource_id)
    raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported expression {type(expression).__name__}")


def _physical_type(field: PhysicalField) -> OfficialType:
    try:
        return _TYPE_MAP[field.value_type]
    except KeyError as exc:
        raise PhysicalPlanningError("PHYSICAL_TYPE_UNSUPPORTED", f"unsupported physical type {field.value_type}") from exc


def _apply_call_constraints(predicate, logical_expression, catalog: PhysicalCatalog, resource_id: str):
    constraints = []
    seen = set()
    for call in _walk_calls(logical_expression):
        for constraint in _call_constraints(call, catalog, resource_id):
            if constraint.node_id not in seen:
                constraints.append(constraint)
                seen.add(constraint.node_id)
    result = predicate
    for constraint in constraints:
        result = PhysicalBinary("and", result, constraint, BOOLEAN)
    return result


def _call_constraints(call: CallExpr, catalog: PhysicalCatalog, resource_id: str):
    if call.binding is None:
        return ()
    constraints = []
    resource = catalog.resource(resource_id)
    stable_resource_id = resource.anchor_resource_id or resource_id
    market = str(call.binding.slots.get("market", "")).strip()
    if market:
        codes = _market_codes(market)
        constraints.append(
            PhysicalIn(
                PhysicalColumn(stable_resource_id, "mktcode", NUMERIC),
                tuple(PhysicalLiteral(code, NUMERIC) for code in codes),
            )
        )
    date = str(call.binding.slots.get("date", "")).strip()
    if date:
        partition_key = catalog.resource(stable_resource_id).partition_key
        if partition_key is None:
            raise PhysicalPlanningError(
                "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED",
                f"resource {resource_id} has no catalog-declared date column",
            )
        column = PhysicalColumn(stable_resource_id, partition_key, TIME)
        if date in {"今日", "今天", "当前", "最新"}:
            value = PhysicalLatestValue(stable_resource_id, partition_key, TIME)
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            value = PhysicalLiteral(date, TIME)
        else:
            raise PhysicalPlanningError(
                "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED",
                f"date constraint requires normalization before physical planning: {date}",
            )
        constraints.append(PhysicalComparison("=", column, value))
    return tuple(constraints)


def _market_codes(value: str) -> Tuple[int, ...]:
    mapping = {"深": (0,), "沪": (1,), "京": (103,), "沪深": (0, 1), "A股": (0, 1), "沪深京": (0, 1, 103)}
    codes = []
    for item in (part.strip() for part in re.split(r"[|&,，]", value) if part.strip()):
        if item.startswith("^") or item not in mapping:
            raise PhysicalPlanningError("PHYSICAL_MARKET_CONSTRAINT_UNSUPPORTED", f"unsupported market constraint: {item}")
        codes.extend(mapping[item])
    return tuple(sorted(set(codes)))


def _deduplicate_fields(fields: Tuple[PhysicalField, ...]) -> Tuple[PhysicalField, ...]:
    unique = {}
    for field in fields:
        unique[(field.resource_id, field.column)] = field
    return tuple(unique[key] for key in sorted(unique))
