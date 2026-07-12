from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Optional, Tuple

from ..ir import (
    BinaryExpr,
    CallExpr,
    ComparisonExpr,
    LiteralExpr,
    LogicalDomainScan,
    LogicalFilter,
    LogicalConsecutive,
    LogicalExist,
    LogicalLimit,
    LogicalRank,
    LogicalStage,
    RangeExpr,
)
from ..lowering import LoweringResult
from ..types import BOOLEAN, NUMERIC, STRING, TIME, OfficialType
from .catalog import PhysicalCatalog
from .expressions import PhysicalExpressionNode, PhysicalExpressionRegistry
from .ir import (
    PhysicalBinary,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalCoalesce,
    PhysicalFilter,
    PhysicalIn,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalNullIf,
    PhysicalPlan,
    PhysicalPrefixAverage,
    PhysicalRank,
    PhysicalScan,
    PhysicalTemporal,
    PhysicalTemporalWindow,
    PhysicalUnary,
)
from .validate import validate_physical_plan
from .statistics import PhysicalStatisticsSnapshot
from .strategies import PhysicalStrategyRegistry


@dataclass(frozen=True)
class PhysicalDecision:
    resource_id: Optional[str]
    feasible: bool
    cost: Optional[float]
    estimated: bool
    reason_code: str
    reason: str
    cost_unit: str = "catalog_priority"
    cost_components: Tuple[Tuple[str, float], ...] = ()
    strategy_id: str = "direct_column"
    selected: bool = False
    selection_eligible: bool = True


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
    selected_strategy: str = "direct_column"


@dataclass(frozen=True)
class _ResolvedIndicator:
    indicator_id: str
    resource_id: str
    value_type: str
    direct_column: Optional[str] = None
    expression: Optional[PhysicalExpressionNode] = None

    @property
    def required_columns(self) -> Tuple[Tuple[str, str], ...]:
        if self.direct_column is not None:
            return ((self.direct_column, self.value_type),)
        assert self.expression is not None
        return self.expression.required_columns


_TYPE_MAP = {
    "boolean": BOOLEAN,
    "numeric": NUMERIC,
    "string": STRING,
    "time": TIME,
}
_DIRECT_FIELD_CALLS = {"indicator", "queryData", "rank"}


def plan_physical(
    lowering: LoweringResult,
    catalog: PhysicalCatalog,
    *,
    statistics: Optional[PhysicalStatisticsSnapshot] = None,
    strategies: Optional[PhysicalStrategyRegistry] = None,
    expressions: Optional[PhysicalExpressionRegistry] = None,
    allow_shadow_strategies: bool = False,
) -> PhysicalPlanningResult:
    fields = _collect_fields(lowering.plan, catalog, expressions)
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
    validate_physical_plan(plan, catalog, expressions)
    direct_decision = _candidate_decision(resource, catalog, statistics)
    base_strategy = "controlled_expression" if any(field.expression is not None for field in fields) else "direct_column"
    candidates = [(plan, selected, base_strategy, direct_decision)]

    indicator_ids = {field.indicator_id.casefold() for field in fields}
    if strategies is not None and len(indicator_ids) == 1:
        indicator_id = fields[0].indicator_id
        for strategy in strategies.strategies_for(indicator_id):
            expression = PhysicalPrefixAverage(
                strategy.prefix_resource_id,
                strategy.sum_column,
                strategy.count_column,
                strategy.window,
                strategy.scale_divisor,
                NUMERIC,
            )
            prefix_plan = _lower_plan(
                lowering.plan,
                catalog,
                strategy.scan_resource_id,
                (),
                expression_overrides={indicator_id.casefold(): expression},
            )
            validate_physical_plan(prefix_plan, catalog, expressions)
            decision = _prefix_candidate_decision(strategy, catalog, statistics, allow_shadow_strategies)
            candidates.append((prefix_plan, strategy.scan_resource_id, strategy.strategy_id, decision))

    candidates.sort(
        key=lambda item: (
            not item[3].selection_eligible,
            item[3].estimated,
            float("inf") if item[3].cost is None else item[3].cost,
            item[2],
        )
    )
    chosen_plan, chosen_resource, chosen_strategy, _ = candidates[0]
    decisions = tuple(
        replace(item[3], strategy_id=item[2], selected=index == 0)
        for index, item in enumerate(candidates)
    )
    return PhysicalPlanningResult(chosen_plan, chosen_resource, decisions, chosen_strategy)


def _candidate_decision(resource, catalog, statistics):
    required = [resource.resource_id]
    if resource.anchor_resource_id:
        required.append(resource.anchor_resource_id)
    if statistics is not None:
        components = []
        missing = []
        for resource_id in required:
            try:
                item = statistics.resource(resource_id)
            except KeyError:
                missing.append(resource_id)
                continue
            if not item.row_count_available:
                missing.append(resource_id)
                continue
            components.append((resource_id, float(item.data_size_bytes)))
        if not missing:
            return PhysicalDecision(
                resource_id=resource.resource_id,
                feasible=True,
                cost=sum(value for _, value in components),
                estimated=False,
                reason_code="PHYSICAL_STATISTICS_CANDIDATE_SELECTED",
                reason="cost is the catalog-declared primary and anchor resource scan bytes",
                cost_unit="bytes",
                cost_components=tuple(components),
            )
        return PhysicalDecision(
            resource_id=resource.resource_id,
            feasible=True,
            cost=float(resource.priority),
            estimated=True,
            reason_code="PHYSICAL_STATISTICS_INCOMPLETE",
            reason=f"catalog priority fallback; missing available row-count statistics for {', '.join(missing)}",
        )
    return PhysicalDecision(
        resource_id=resource.resource_id,
        feasible=True,
        cost=float(resource.priority),
        estimated=True,
        reason_code="PHYSICAL_CANDIDATE_SELECTED",
        reason="catalog priority used because runtime statistics are unavailable",
    )


def _prefix_candidate_decision(strategy, catalog, statistics, allow_shadow_strategies):
    scan = catalog.resource(strategy.scan_resource_id)
    prefix = catalog.resource(strategy.prefix_resource_id)
    if statistics is not None:
        try:
            scan_stats = statistics.resource(scan.resource_id)
            prefix_stats = statistics.resource(prefix.resource_id)
        except KeyError:
            pass
        else:
            if scan_stats.row_count_available and prefix_stats.row_count_available:
                components = (
                    (scan.resource_id, float(scan_stats.data_size_bytes)),
                    (prefix.resource_id, float(prefix_stats.data_size_bytes * 2)),
                )
                return PhysicalDecision(
                    resource_id=prefix.resource_id,
                    feasible=True,
                    cost=sum(value for _, value in components),
                    estimated=False,
                    reason_code=(
                        "PHYSICAL_PREFIX_CANDIDATE_SELECTED"
                        if strategy.selection_mode == "active" or allow_shadow_strategies
                        else "PHYSICAL_PREFIX_SHADOW_CANDIDATE"
                    ),
                    reason=(
                        "cost is scan bytes plus two conservative prefix resource accesses; "
                        f"selection mode is {strategy.selection_mode}"
                    ),
                    cost_unit="bytes",
                    cost_components=components,
                    selection_eligible=strategy.selection_mode == "active" or allow_shadow_strategies,
                )
    return PhysicalDecision(
        resource_id=prefix.resource_id,
        feasible=True,
        cost=float(scan.priority + prefix.priority * 2),
        estimated=True,
        reason_code="PHYSICAL_PREFIX_STATISTICS_INCOMPLETE",
        reason="catalog priority fallback for prefix candidate",
        selection_eligible=strategy.selection_mode == "active" or allow_shadow_strategies,
    )


def _collect_fields(
    plan,
    catalog: PhysicalCatalog,
    expressions: Optional[PhysicalExpressionRegistry],
) -> Tuple[_ResolvedIndicator, ...]:
    logical_expressions = []
    current = plan
    while isinstance(current, (LogicalFilter, LogicalLimit, LogicalRank, LogicalStage, LogicalConsecutive, LogicalExist)):
        if isinstance(current, LogicalFilter):
            logical_expressions.append(current.predicate)
        elif isinstance(current, (LogicalConsecutive, LogicalExist)):
            logical_expressions.append(current.spec.predicate)
        elif isinstance(current, LogicalRank):
            logical_expressions.append(current.order_by)
        current = current.operation if isinstance(current, LogicalStage) else current.input
    if not isinstance(current, LogicalDomainScan):
        raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical root {type(current).__name__}")

    fields = []
    for expression in logical_expressions:
        for call in _walk_calls(expression):
            if call.name not in _DIRECT_FIELD_CALLS or call.binding is None:
                raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {call.name}")
            _reject_unmaterialized_constraints(call)
            indicator_id = call.binding.slots.get("indicator_name", "")
            try:
                fields.append(_resolve_indicator(indicator_id, catalog, expressions))
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


def _lower_plan(
    plan,
    catalog: PhysicalCatalog,
    resource_id: str,
    fields: Tuple[_ResolvedIndicator, ...],
    expression_overrides=None,
) -> PhysicalPlan:
    if isinstance(plan, LogicalDomainScan):
        columns = _scan_columns(fields)
        resource = catalog.resource(resource_id)
        return PhysicalScan(resource_id, columns, None, resource.anchor_resource_id)
    if isinstance(plan, LogicalFilter):
        return PhysicalFilter(
            _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides),
            _lower_expr(plan.predicate, catalog, resource_id, fields, expression_overrides=expression_overrides),
        )
    if isinstance(plan, LogicalLimit):
        return PhysicalLimit(
            _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides),
            plan.offset,
            plan.count,
        )
    if isinstance(plan, LogicalRank):
        input_plan = _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides)
        if isinstance(input_plan, PhysicalRank):
            raise PhysicalPlanningError(
                "PHYSICAL_CHAINED_RANK_UNSUPPORTED",
                "chained rank requires explicit stage-output alias propagation",
            )
        for constraint in _call_constraints(plan.order_by, catalog, resource_id):
            input_plan = PhysicalFilter(input_plan, constraint)
        expression = _lower_expr(plan.order_by, catalog, resource_id, fields, allow_rank=True, expression_overrides=expression_overrides)
        bound = _lower_expr(plan.bound, catalog, resource_id, fields, expression_overrides=expression_overrides)
        if not isinstance(bound, PhysicalLiteral) or not isinstance(bound.value, (int, float)):
            raise PhysicalPlanningError("PHYSICAL_RANK_BOUND_UNSUPPORTED", "physical rank requires a numeric literal bound")
        return PhysicalRank(input_plan, expression, plan.direction, bound, plan.comparator)
    if isinstance(plan, (LogicalConsecutive, LogicalExist)):
        if plan.spec.unit not in {"", "日"}:
            raise PhysicalPlanningError(
                "PHYSICAL_TEMPORAL_BUCKET_UNSUPPORTED",
                f"temporal unit {plan.spec.unit} requires calendar bucket materialization",
            )
        return PhysicalTemporal(
            _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides),
            _lower_expr(plan.spec.predicate, catalog, resource_id, fields, expression_overrides=expression_overrides),
            "CONS" if isinstance(plan, LogicalConsecutive) else "EXIST",
            plan.spec.comparator,
            plan.spec.threshold,
            plan.spec.maximum,
            plan.spec.unit,
            plan.spec.every,
            _lower_temporal_window(plan.spec.window),
            plan.spec.trading_sequence,
        )
    if isinstance(plan, LogicalStage):
        return _lower_plan(plan.operation, catalog, resource_id, fields, expression_overrides)
    raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical node {type(plan).__name__}")


def _lower_temporal_window(window) -> PhysicalTemporalWindow:
    if window.kind == "unspecified":
        return PhysicalTemporalWindow("all_history")
    if window.kind == "relative" and window.anchor == "today":
        return PhysicalTemporalWindow("latest_session", lookback_sessions=1)
    if window.kind == "exact" and window.start and window.end:
        return PhysicalTemporalWindow("exact_date", start=window.start, end=window.end)
    if window.kind == "calendar_range" and window.start and window.end:
        return PhysicalTemporalWindow("calendar_range", start=window.start, end=window.end)
    if window.kind == "recent_sessions" and window.amount:
        return PhysicalTemporalWindow("recent_sessions", lookback_sessions=window.amount)
    if window.kind == "recent_calendar" and window.amount and window.unit:
        return PhysicalTemporalWindow(
            "recent_calendar",
            calendar_amount=window.amount,
            calendar_unit=window.unit,
        )
    if window.kind == "expression" and window.anchor:
        text = str(window.anchor).strip()
        match = re.fullmatch(r"(?:最近|近)(\d+)(?:日|天)|(?:(\d+)(?:日|天)(?:内|以内))", text)
        if match:
            return PhysicalTemporalWindow("recent_sessions", lookback_sessions=int(match.group(1) or match.group(2)))
    raise PhysicalPlanningError(
        "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED",
        f"temporal date window requires typed normalization: {window.anchor or window.start or window.kind}",
    )


def _lower_expr(
    expression,
    catalog: PhysicalCatalog,
    resource_id: str,
    fields: Tuple[_ResolvedIndicator, ...],
    *,
    allow_rank: bool = False,
    expression_overrides=None,
):
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
        if expression_overrides and indicator_id.casefold() in expression_overrides:
            return expression_overrides[indicator_id.casefold()]
        try:
            field = _field_for_indicator(fields, indicator_id)
        except KeyError as exc:
            raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", f"no controlled physical mapping for indicator {indicator_id}") from exc
        if field.resource_id != resource_id:
            raise PhysicalPlanningError("PHYSICAL_MULTI_RESOURCE_UNSUPPORTED", "expression spans multiple physical resources")
        if field.direct_column is not None:
            return PhysicalColumn(field.resource_id, field.direct_column, _type_from_name(field.value_type))
        assert field.expression is not None
        return _lower_declared_expression(field.expression, field.resource_id)
    if isinstance(expression, BinaryExpr):
        return PhysicalBinary(
            expression.op,
            _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides),
            _lower_expr(expression.right, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides),
            expression.type,
        )
    if isinstance(expression, ComparisonExpr):
        if expression.op == "~=":
            raise PhysicalPlanningError(
                "PHYSICAL_APPROXIMATION_POLICY_MISSING",
                "approximate comparison requires catalog-provided absolute and relative tolerances",
            )
        if isinstance(expression.right, RangeExpr) and expression.op == "between":
            value = _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides)
            lower = _lower_expr(expression.right.lower, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides)
            upper = _lower_expr(expression.right.upper, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides)
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
                _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides),
                _lower_expr(expression.right, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides),
            )
        return _apply_call_constraints(result, expression, catalog, resource_id)
    raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported expression {type(expression).__name__}")


def _type_from_name(value_type: str) -> OfficialType:
    try:
        return _TYPE_MAP[value_type]
    except KeyError as exc:
        raise PhysicalPlanningError("PHYSICAL_TYPE_UNSUPPORTED", f"unsupported physical type {value_type}") from exc


def _resolve_indicator(
    indicator_id: str,
    catalog: PhysicalCatalog,
    expressions: Optional[PhysicalExpressionRegistry],
) -> _ResolvedIndicator:
    try:
        field = catalog.indicator(indicator_id)
    except KeyError:
        if expressions is None:
            raise
        definition = expressions.resolve(indicator_id)
        return _ResolvedIndicator(
            definition.indicator_id,
            definition.resource_id,
            definition.value_type,
            expression=definition.expression,
        )
    return _ResolvedIndicator(
        field.indicator_id,
        field.resource_id,
        field.value_type,
        direct_column=field.column,
    )


def _field_for_indicator(
    fields: Tuple[_ResolvedIndicator, ...],
    indicator_id: str,
) -> _ResolvedIndicator:
    folded = indicator_id.casefold()
    for field in fields:
        if field.indicator_id.casefold() == folded:
            return field
    raise KeyError(indicator_id)


def _scan_columns(fields: Tuple[_ResolvedIndicator, ...]) -> Tuple[PhysicalColumn, ...]:
    columns = {}
    for field in fields:
        for column, value_type in field.required_columns:
            key = (field.resource_id, column)
            physical_type = _type_from_name(value_type)
            if key in columns and columns[key].type is not physical_type:
                raise PhysicalPlanningError(
                    "PHYSICAL_COLUMN_TYPE_CONFLICT",
                    f"conflicting physical types for {field.resource_id}.{column}",
                )
            columns[key] = PhysicalColumn(field.resource_id, column, physical_type)
    return tuple(columns[key] for key in sorted(columns))


def _lower_declared_expression(
    expression: PhysicalExpressionNode,
    resource_id: str,
):
    value_type = _type_from_name(expression.type)
    if expression.op == "column":
        return PhysicalColumn(resource_id, expression.column, value_type)
    if expression.op == "literal":
        return PhysicalLiteral(expression.value, value_type)
    if expression.op == "negate":
        return PhysicalUnary(
            "negate",
            _lower_declared_expression(expression.args[0], resource_id),
            value_type,
        )
    if expression.op == "coalesce":
        return PhysicalCoalesce(
            tuple(_lower_declared_expression(item, resource_id) for item in expression.args),
            value_type,
        )
    left = _lower_declared_expression(expression.args[0], resource_id)
    right = _lower_declared_expression(expression.args[1], resource_id)
    binary = {
        "add": "+",
        "subtract": "-",
        "multiply": "*",
        "divide": "/",
        "and": "and",
        "or": "or",
    }
    comparison = {
        "equal": "=",
        "not_equal": "!=",
        "greater": ">",
        "greater_equal": ">=",
        "less": "<",
        "less_equal": "<=",
    }
    if expression.op == "safe_divide":
        return PhysicalBinary(
            "/",
            left,
            PhysicalNullIf(right, PhysicalLiteral(0, NUMERIC), NUMERIC),
            NUMERIC,
        )
    if expression.op in binary:
        return PhysicalBinary(binary[expression.op], left, right, value_type)
    if expression.op in comparison:
        return PhysicalComparison(comparison[expression.op], left, right)
    raise PhysicalPlanningError(
        "PHYSICAL_EXPRESSION_OPERATOR_UNSUPPORTED",
        f"unsupported controlled expression operator {expression.op}",
    )


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
