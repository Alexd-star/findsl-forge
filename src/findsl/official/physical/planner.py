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
    LogicalSetOperation,
    RangeExpr,
)
from ..lowering import LoweringResult
from ..domain.binder import parse_date_constraint
from ..domain.market import (
    MarketAnd,
    MarketAtom,
    MarketNot,
    MarketOr,
    parse_market_expression,
)
from ..domain.scope import ScopeAnd, ScopeAtom, ScopeNot, ScopeOr
from ..types import BOOLEAN, NUMERIC, STRING, TIME, OfficialType
from .catalog import PhysicalCatalog
from .expressions import PhysicalExpressionNode, PhysicalExpressionRegistry
from .ir import (
    PhysicalAbs,
    PhysicalBinary,
    PhysicalAggregateGroup,
    PhysicalAggregateRank,
    PhysicalAggregateRef,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalCandidateSetOperation,
    PhysicalCompositeAggregate,
    PhysicalCoalesce,
    PhysicalDynamicDateRange,
    PhysicalEventFilter,
    PhysicalEventProjection,
    PhysicalEventRef,
    PhysicalExternalExists,
    PhysicalCrossing,
    PhysicalExtreme,
    PhysicalFilter,
    PhysicalGroupedAggregate,
    PhysicalGreatest,
    PhysicalIn,
    PhysicalJoin,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalNullIf,
    PhysicalNamedAggregate,
    PhysicalNamedRank,
    PhysicalNamedScalar,
    PhysicalNot,
    PhysicalNthLatestValue,
    PhysicalPlan,
    PhysicalPrefixAverage,
    PhysicalPrefixAggregate,
    PhysicalPrefixJoin,
    PhysicalPrefixRef,
    PhysicalPattern,
    PhysicalPosition,
    PhysicalProjection,
    PhysicalProjectedRef,
    PhysicalRank,
    PhysicalRankExpression,
    PhysicalRecentSessions,
    PhysicalSessionBoundaryRange,
    PhysicalScan,
    PhysicalStageRank,
    PhysicalTableScan,
    PhysicalTemporal,
    PhysicalTemporalAggregate,
    PhysicalTemporalRank,
    PhysicalTemporalWindow,
    PhysicalSetOperation,
    PhysicalUnary,
)
from .validate import validate_physical_plan
from .statistics import PhysicalStatisticsSnapshot
from .strategies import (
    PhysicalMaterializedAggregateStrategy,
    PhysicalPrefixAggregateStrategy,
    PhysicalStrategyRegistry,
)
from .runtime import (
    current_benchmark_policy_catalog,
    current_external_data_policy,
    current_external_index_quote_catalog,
    current_external_scope_catalog,
    current_function_catalog,
    current_numeric_approximation_policy,
    current_physical_pattern_config,
    current_security_scope_catalog,
)
from .scopes import SecurityScopeCatalog


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
class _PlanCandidate:
    plan: PhysicalPlan
    resource_id: str
    strategy_id: str
    decision: PhysicalDecision
    baseline: bool = False


@dataclass(frozen=True)
class _ResolvedIndicator:
    indicator_id: str
    resource_id: str
    value_type: str
    direct_column: Optional[str] = None
    expression: Optional[PhysicalExpressionNode] = None
    prefix_average: Optional[PhysicalPrefixAverage] = None

    @property
    def required_columns(self) -> Tuple[Tuple[str, str], ...]:
        if self.direct_column is not None:
            return ((self.direct_column, self.value_type),)
        if (
            self.indicator_id in {"是否T+0", "稳定证券顺序"}
            or self.prefix_average is not None
        ):
            return ()
        assert self.expression is not None
        return self.expression.required_columns


@dataclass(frozen=True)
class _IndexQuoteBinding:
    index_code: str
    snapshot_id: str


_TYPE_MAP = {
    "boolean": BOOLEAN,
    "numeric": NUMERIC,
    "string": STRING,
    "time": TIME,
}
_DIRECT_FIELD_CALLS = {"indicator", "queryData", "rank"}
_CROSSING_CALLS = {"cross_above", "cross_down", "golden_cross"}
_EXTREME_CALLS = {"record_high", "record_low"}
_PATTERN_CALLS = {"reset", "close_together"}
_POSITION_CALLS = {"position"}
_WINDOW_EVENT_CALLS = _CROSSING_CALLS | _EXTREME_CALLS | _PATTERN_CALLS | _POSITION_CALLS
_SET_AGGREGATE_FUNCTIONS = {
    "SUM",
    "AVG",
    "MAX",
    "MIN",
    "GROWTH_RISE",
    "GROWTH_FALL",
}


def _merge_exist_temporal_union(left, right) -> Optional[PhysicalTemporal]:
    if not isinstance(left, PhysicalTemporal) or not isinstance(right, PhysicalTemporal):
        return None
    if not isinstance(left.input, PhysicalEventProjection) or not isinstance(
        right.input, PhysicalEventProjection
    ):
        return None
    if (
        left.mode != "EXIST"
        or left.comparator != ">"
        or left.threshold != 0
        or left.maximum is not None
        or left.every
        or right.mode != left.mode
        or right.comparator != left.comparator
        or right.threshold != left.threshold
        or right.maximum != left.maximum
        or right.every != left.every
        or right.unit != left.unit
        or right.window != left.window
        or right.trading_sequence != left.trading_sequence
        or right.scalars != left.scalars
        or right.input.input != left.input.input
        or right.input.projections != left.input.projections
    ):
        return None

    aliases = {event.alias for event in left.input.events}
    renamed_events = []
    alias_map = {}
    for event in right.input.events:
        alias = event.alias
        suffix = 1
        while alias in aliases:
            alias = f"{event.alias}_{suffix}"
            suffix += 1
        aliases.add(alias)
        alias_map[event.alias] = alias
        renamed_events.append(replace(event, alias=alias))
    right_predicate = _rename_event_refs(right.predicate, alias_map)
    merged_input = PhysicalEventProjection(
        left.input.input,
        left.input.events + tuple(renamed_events),
        left.input.projections,
    )
    return replace(
        left,
        input=merged_input,
        predicate=PhysicalBinary(
            "or",
            left.predicate,
            right_predicate,
            BOOLEAN,
        ),
    )


def _rename_event_refs(expression, aliases):
    if isinstance(expression, PhysicalEventRef):
        return replace(expression, alias=aliases.get(expression.alias, expression.alias))
    if isinstance(expression, PhysicalBinary):
        return replace(
            expression,
            left=_rename_event_refs(expression.left, aliases),
            right=_rename_event_refs(expression.right, aliases),
        )
    if isinstance(expression, PhysicalComparison):
        return replace(
            expression,
            left=_rename_event_refs(expression.left, aliases),
            right=_rename_event_refs(expression.right, aliases),
        )
    if isinstance(expression, PhysicalNot):
        return replace(
            expression,
            operand=_rename_event_refs(expression.operand, aliases),
        )
    return expression


def plan_physical(
    lowering: LoweringResult,
    catalog: PhysicalCatalog,
    *,
    statistics: Optional[PhysicalStatisticsSnapshot] = None,
    strategies: Optional[PhysicalStrategyRegistry] = None,
    expressions: Optional[PhysicalExpressionRegistry] = None,
    allow_shadow_strategies: bool = False,
) -> PhysicalPlanningResult:
    if isinstance(lowering.plan, LogicalLimit) and isinstance(
        lowering.plan.input,
        (LogicalSetOperation, LogicalStage),
    ):
        inner = plan_physical(
            replace(lowering, plan=lowering.plan.input),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        plan = PhysicalLimit(inner.plan, lowering.plan.offset, lowering.plan.count)
        validate_physical_plan(plan, catalog, expressions)
        return replace(inner, plan=plan, selected_strategy=f"limit_{inner.selected_strategy}")
    if isinstance(lowering.plan, LogicalStage) and isinstance(
        lowering.plan.operation,
        LogicalSetOperation,
    ):
        return plan_physical(
            replace(lowering, plan=lowering.plan.operation),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
    if isinstance(lowering.plan, LogicalSetOperation):
        left = plan_physical(
            replace(lowering, plan=lowering.plan.left),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        right = plan_physical(
            replace(lowering, plan=lowering.plan.right),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        merged_temporal = (
            _merge_exist_temporal_union(left.plan, right.plan)
            if lowering.plan.operation == "union"
            else None
        )
        if merged_temporal is not None:
            validate_physical_plan(merged_temporal, catalog, expressions)
            decisions = tuple(
                replace(item, strategy_id=f"shared_left:{item.strategy_id}")
                for item in left.decisions
            ) + tuple(
                replace(item, strategy_id=f"shared_right:{item.strategy_id}")
                for item in right.decisions
            )
            resources = "+".join(
                sorted({left.selected_resource, right.selected_resource})
            )
            return PhysicalPlanningResult(
                merged_temporal,
                resources,
                decisions,
                "shared_temporal_union",
            )
        plan = PhysicalSetOperation(left.plan, right.plan, lowering.plan.operation)
        validate_physical_plan(plan, catalog, expressions)
        decisions = tuple(
            replace(item, strategy_id=f"left:{item.strategy_id}")
            for item in left.decisions
        ) + tuple(
            replace(item, strategy_id=f"right:{item.strategy_id}")
            for item in right.decisions
        )
        resources = "+".join(sorted({left.selected_resource, right.selected_resource}))
        return PhysicalPlanningResult(
            plan,
            resources,
            decisions,
            f"set_{lowering.plan.operation}",
        )
    _validate_universe_contract(lowering.plan)
    event_composition = _event_composition_contract(lowering.plan)
    if event_composition is not None:
        input_plan, event_predicate, other_predicate, operation, limit = event_composition
        event_logical = LogicalFilter(input_plan, event_predicate, input_plan.schema)
        other_logical = LogicalFilter(input_plan, other_predicate, input_plan.schema)
        event_result = plan_physical(
            replace(lowering, plan=event_logical),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        other_result = plan_physical(
            replace(lowering, plan=other_logical),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        plan: PhysicalPlan = PhysicalCandidateSetOperation(
            event_result.plan,
            other_result.plan,
            operation,
            "official_basic",
        )
        if limit is not None:
            plan = PhysicalLimit(plan, limit[0], limit[1])
        validate_physical_plan(plan, catalog, expressions)
        decisions = tuple(
            replace(item, strategy_id=f"event:{item.strategy_id}")
            for item in event_result.decisions
        ) + tuple(
            replace(item, strategy_id=f"candidate:{item.strategy_id}")
            for item in other_result.decisions
        )
        resources = "+".join(
            sorted({event_result.selected_resource, other_result.selected_resource})
        )
        return PhysicalPlanningResult(
            plan,
            resources,
            decisions,
            f"event_candidate_{operation}",
        )
    aggregate_calls = _aggregate_calls(lowering.plan)
    querydata_scalar_calls = _querydata_scalar_calls(lowering.plan)
    aggregate_contract = _aggregate_contract(lowering.plan, aggregate_calls)
    aggregate_rank_contract = _aggregate_rank_contract(lowering.plan)
    temporal_aggregate_contract = _temporal_aggregate_contract(lowering.plan)
    temporal_scalar_contract = _temporal_scalar_contract(lowering.plan)
    temporal_rank_contract = _temporal_rank_contract(lowering.plan)
    rank_expression_contract = _rank_expression_contract(lowering.plan)
    fields = _collect_fields(lowering.plan, catalog, expressions)
    resource_ids = tuple(sorted({field.resource_id for field in fields}))
    if not resource_ids:
        if _contains_universe_selector(lowering.plan):
            resource_ids = ("official_basic",)
        else:
            raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", "logical plan has no directly mapped physical indicator")
    if _is_top_level_stage_rank(lowering.plan):
        current = lowering.plan.input if isinstance(lowering.plan, LogicalLimit) else lowering.plan
        prior = plan_physical(
            replace(lowering, plan=current.input),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        plan = _build_stage_rank(
            prior.plan,
            current.operation,
            catalog,
            fields,
        )
        if isinstance(lowering.plan, LogicalLimit):
            plan = PhysicalLimit(plan, lowering.plan.offset, lowering.plan.count)
        validate_physical_plan(plan, catalog, expressions)
        return PhysicalPlanningResult(
            plan,
            prior.selected_resource,
            prior.decisions,
            "stage_rank",
        )
    crossing_calls = _crossing_calls(lowering.plan)
    if crossing_calls:
        temporal_root = (
            lowering.plan.input
            if isinstance(lowering.plan, LogicalLimit)
            else lowering.plan
        )
        if isinstance(temporal_root, (LogicalConsecutive, LogicalExist)):
            return _plan_temporal_crossing_events(
                lowering,
                crossing_calls,
                catalog,
                fields,
                resource_ids,
                expressions,
            )
        return _plan_crossing_events(
            lowering,
            crossing_calls,
            catalog,
            fields,
            resource_ids,
            expressions,
        )
    if temporal_aggregate_contract is not None:
        return _plan_temporal_aggregate(
            temporal_aggregate_contract,
            catalog,
            fields,
            resource_ids,
            expressions,
            statistics,
        )
    if temporal_scalar_contract is not None:
        return _plan_temporal_scalar(
            temporal_scalar_contract,
            catalog,
            fields,
            expressions,
            statistics,
        )
    if temporal_rank_contract is not None:
        return _plan_temporal_rank(
            temporal_rank_contract,
            catalog,
            fields,
            resource_ids,
            expressions,
            statistics,
        )
    if rank_expression_contract is not None:
        return _plan_rank_expression(
            lowering,
            rank_expression_contract,
            catalog,
            fields,
            expressions,
            statistics,
            strategies,
            allow_shadow_strategies,
        )
    if aggregate_rank_contract is not None:
        return _plan_aggregate_rank(
            aggregate_rank_contract,
            catalog,
            fields,
            expressions,
            statistics,
        )
    if aggregate_contract is not None:
        return _plan_grouped_aggregate(
            lowering.plan,
            aggregate_contract,
            catalog,
            fields,
            resource_ids,
            expressions,
            statistics,
            strategies,
            allow_shadow_strategies,
        )
    if aggregate_calls or querydata_scalar_calls:
        return _plan_composite_aggregate(
            lowering.plan,
            aggregate_calls,
            querydata_scalar_calls,
            catalog,
            fields,
            expressions,
            statistics,
        )
    if len(resource_ids) > 1:
        return _plan_multi_resource(lowering, catalog, fields, resource_ids, expressions)

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
    plan = _with_dynamic_prefixes(plan, fields)
    if _needs_implicit_latest_snapshot(lowering.plan):
        plan = _with_latest_snapshot(plan, catalog, selected)
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
            prefix_alias = "prefix_value"
            prefix_plan = _lower_plan(
                lowering.plan,
                catalog,
                strategy.scan_resource_id,
                (),
                expression_overrides={
                    indicator_id.casefold(): PhysicalPrefixRef(
                        prefix_alias,
                        NUMERIC,
                    )
                },
            )
            if _needs_implicit_latest_snapshot(lowering.plan):
                prefix_plan = _with_latest_snapshot(
                    prefix_plan,
                    catalog,
                    strategy.scan_resource_id,
                )
            prefix_plan = _materialize_prefix_join(
                prefix_plan,
                PhysicalProjection(prefix_alias, expression),
            )
            validate_physical_plan(prefix_plan, catalog, expressions)
            decision = _prefix_candidate_decision(
                strategy,
                catalog,
                statistics,
                allow_shadow_strategies,
                default_eligible=_is_prefix_filter_plan(prefix_plan),
            )
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


def _materialize_prefix_join(
    plan: PhysicalPlan,
    projection: PhysicalProjection,
) -> PhysicalPlan:
    if isinstance(plan, PhysicalLimit):
        return replace(
            plan,
            input=_materialize_prefix_join(plan.input, projection),
        )
    if isinstance(plan, PhysicalFilter):
        return PhysicalPrefixJoin(
            plan.input,
            (projection,),
            plan.predicate,
        )
    if isinstance(plan, PhysicalRank):
        return replace(
            plan,
            input=PhysicalPrefixJoin(
                plan.input,
                (projection,),
                None,
            ),
        )
    raise PhysicalPlanningError(
        "PHYSICAL_PREFIX_RELATION_UNAVAILABLE",
        "prefix strategy requires a filter or rank relation",
    )


def _is_prefix_filter_plan(plan: PhysicalPlan) -> bool:
    current = plan.input if isinstance(plan, PhysicalLimit) else plan
    return isinstance(current, PhysicalPrefixJoin) and current.predicate is not None


@dataclass(frozen=True)
class _AggregateContract:
    call: CallExpr
    comparator: str
    bound: LiteralExpr
    function: str
    limit: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class _AggregateRankContract:
    call: CallExpr
    direction: str
    bound: LiteralExpr
    comparator: str
    upper_bound: Optional[LiteralExpr]
    lower_inclusive: bool
    upper_inclusive: bool
    limit: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class _TemporalAggregateContract:
    call: CallExpr
    function: str
    value_comparator: str
    value_bound: LiteralExpr
    temporal_plan: object
    limit: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class _TemporalScalarContract:
    left: CallExpr
    right: CallExpr
    comparator: str
    temporal_plan: object
    limit: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class _TemporalRankContract:
    call: CallExpr
    aggregate_function: Optional[str]
    direction: str
    rank_comparator: str
    rank_bound: LiteralExpr
    rank_upper_bound: Optional[LiteralExpr]
    rank_lower_inclusive: bool
    rank_upper_inclusive: bool
    temporal_plan: object
    limit: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class _RankExpressionContract:
    predicate: object
    calls: Tuple[CallExpr, ...]
    input_plan: object
    limit: Optional[Tuple[int, int]] = None


def _aggregate_calls(plan) -> Tuple[CallExpr, ...]:
    return tuple(
        call
        for expression in _logical_expressions(plan)
        for call in _walk_calls(expression)
        if call.binding is not None
        and (
            call.name == "belong_industry"
            or str(call.binding.slots.get("agg_func", "")).strip()
        )
    )


def _querydata_scalar_calls(plan) -> Tuple[CallExpr, ...]:
    return tuple(
        call
        for expression in _logical_expressions(plan)
        for call in _walk_calls(expression)
        if call.name == "queryData"
        and call.binding is not None
        and call.scope_expression is not None
        and not str(call.binding.slots.get("agg_func", "")).strip()
    )


def _aggregate_contract(
    plan,
    calls: Tuple[CallExpr, ...],
) -> Optional[_AggregateContract]:
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not calls:
        return None
    functions = {
        (
            str(call.binding.slots.get("agg_func", "")).strip().upper()
            or ("AVG" if call.name == "belong_industry" else "")
        )
        for call in calls
    }
    unsupported = sorted(functions - _SET_AGGREGATE_FUNCTIONS)
    if unsupported:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
            f"aggregate function requires a dedicated contract: {', '.join(unsupported)}",
        )
    if len(calls) != 1:
        return None
    if calls[0].name == "belong_industry":
        return None
    if not isinstance(current, LogicalFilter) or not isinstance(current.predicate, ComparisonExpr):
        return None
    predicate = current.predicate
    if predicate.left is not calls[0] or not isinstance(predicate.right, LiteralExpr):
        return None
    return _AggregateContract(
        calls[0],
        predicate.op,
        predicate.right,
        next(iter(functions)).lower(),
        limit,
    )


def _aggregate_rank_contract(plan) -> Optional[_AggregateRankContract]:
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, LogicalRank) or not isinstance(current.order_by, CallExpr):
        return None
    call = current.order_by
    if call.binding is None or not str(call.binding.slots.get("agg_func", "")).strip():
        return None
    if not isinstance(current.bound, LiteralExpr):
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_BOUND_UNSUPPORTED",
            "aggregate rank requires a literal bound",
        )
    if current.upper_bound is not None and not isinstance(
        current.upper_bound, LiteralExpr
    ):
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_BOUND_UNSUPPORTED",
            "aggregate rank upper bound must be a literal",
        )
    return _AggregateRankContract(
        call,
        current.direction,
        current.bound,
        current.comparator,
        current.upper_bound,
        current.lower_inclusive,
        current.upper_inclusive,
        limit,
    )


def _temporal_aggregate_contract(plan) -> Optional[_TemporalAggregateContract]:
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, (LogicalConsecutive, LogicalExist)):
        return None
    predicate = current.spec.predicate
    if not isinstance(predicate, ComparisonExpr):
        return None
    if not isinstance(predicate.left, CallExpr) or not isinstance(predicate.right, LiteralExpr):
        return None
    call = predicate.left
    if call.binding is None:
        return None
    if call.name == "rank":
        return None
    function = str(call.binding.slots.get("agg_func", "")).strip().upper()
    if not function:
        return None
    if function not in _SET_AGGREGATE_FUNCTIONS:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
            f"temporal aggregate function requires a dedicated contract: {function}",
        )
    if predicate.op not in {"<", "<=", "=", "!=", ">", ">="}:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_COMPOSITION_UNSUPPORTED",
            "temporal aggregate currently requires a scalar comparison bound",
        )
    return _TemporalAggregateContract(
        call,
        function.lower(),
        predicate.op,
        predicate.right,
        current,
        limit,
    )


def _temporal_scalar_contract(plan) -> Optional[_TemporalScalarContract]:
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, (LogicalConsecutive, LogicalExist)):
        return None
    predicate = current.spec.predicate
    if not (
        isinstance(predicate, ComparisonExpr)
        and isinstance(predicate.left, CallExpr)
        and isinstance(predicate.right, CallExpr)
        and predicate.right.name == "queryData"
        and predicate.right.binding is not None
    ):
        return None
    function = str(
        predicate.right.binding.slots.get("agg_func", "")
    ).strip().upper()
    if function not in _SET_AGGREGATE_FUNCTIONS:
        return None
    return _TemporalScalarContract(
        predicate.left,
        predicate.right,
        predicate.op,
        current,
        limit,
    )


def _temporal_rank_contract(plan) -> Optional[_TemporalRankContract]:
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, (LogicalConsecutive, LogicalExist)):
        return None
    predicate = current.spec.predicate
    if not isinstance(predicate, ComparisonExpr):
        return None
    if not isinstance(predicate.left, CallExpr) or predicate.left.name != "rank":
        return None
    if isinstance(predicate.right, RangeExpr) and predicate.op == "between":
        if not isinstance(predicate.right.lower, LiteralExpr) or not isinstance(
            predicate.right.upper, LiteralExpr
        ):
            return None
        rank_bound = predicate.right.lower
        rank_upper_bound = predicate.right.upper
        lower_inclusive = predicate.right.lower_inclusive
        upper_inclusive = predicate.right.upper_inclusive
    elif isinstance(predicate.right, LiteralExpr):
        rank_bound = predicate.right
        rank_upper_bound = None
        lower_inclusive = True
        upper_inclusive = True
    else:
        return None
    call = predicate.left
    if call.binding is None:
        return None
    function = str(call.binding.slots.get("agg_func", "")).strip().upper() or None
    if function is not None and function not in _SET_AGGREGATE_FUNCTIONS:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
            f"temporal rank aggregate requires a dedicated contract: {function}",
        )
    if predicate.op not in {"<", "<=", "=", "!=", ">", ">=", "between"}:
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
            "temporal rank requires one scalar rank bound",
        )
    direction = str(call.binding.slots.get("direction", "")).strip().lower()
    if direction not in {"asc", "desc"}:
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_DIRECTION_UNSUPPORTED",
            f"unsupported temporal rank direction: {direction}",
        )
    return _TemporalRankContract(
        call,
        function.lower() if function else None,
        direction,
        predicate.op,
        rank_bound,
        rank_upper_bound,
        lower_inclusive,
        upper_inclusive,
        current,
        limit,
    )


def _rank_expression_contract(plan) -> Optional[_RankExpressionContract]:
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if isinstance(current, LogicalStage):
        current = current.operation
    if not isinstance(current, LogicalFilter):
        return None
    calls = tuple(
        call for call in _walk_calls(current.predicate) if call.name == "rank"
    )
    if not calls:
        return None
    return _RankExpressionContract(
        current.predicate,
        calls,
        current.input,
        limit,
    )


def _is_top_level_stage_rank(plan) -> bool:
    current = plan.input if isinstance(plan, LogicalLimit) else plan
    return isinstance(current, LogicalStage) and isinstance(
        current.operation, LogicalRank
    )


def _plan_temporal_scalar(
    contract: _TemporalScalarContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
) -> PhysicalPlanningResult:
    left_id = contract.left.binding.slots.get("indicator_name", "")
    right_id = contract.right.binding.slots.get("indicator_name", "")
    left_field = _field_for_indicator(fields, left_id)
    right_field = _field_for_indicator(fields, right_id)
    if left_field.resource_id != right_field.resource_id:
        raise PhysicalPlanningError(
            "PHYSICAL_TEMPORAL_SCALAR_RESOURCE_MISMATCH",
            "cross-scope temporal scalar currently requires one quote resource",
        )
    resource_id = left_field.resource_id
    resource = catalog.resource(resource_id)
    left_input: PhysicalPlan = PhysicalScan(
        resource_id,
        _scan_columns((left_field,)),
        None,
        resource.anchor_resource_id,
    )
    for constraint in _call_constraints(contract.left, catalog, resource_id):
        left_input = PhysicalFilter(left_input, constraint)

    scalar_input: PhysicalPlan = PhysicalScan(
        resource_id,
        _scan_columns((right_field,)),
        None,
        resource.anchor_resource_id,
    )
    for constraint in _call_constraints(contract.right, catalog, resource_id):
        scalar_input = PhysicalFilter(scalar_input, constraint)
    function = str(
        contract.right.binding.slots.get("agg_func", "")
    ).strip().lower()
    scalar = PhysicalNamedScalar(
        "temporal_scalar_0",
        scalar_input,
        _physical_field_expression(right_field),
        "temporal_scalar_value_0",
        False,
        False,
        function,
    )
    predicate = PhysicalComparison(
        contract.comparator,
        _physical_field_expression(left_field),
        PhysicalAggregateRef(
            scalar.alias,
            scalar.value_alias,
            _type_from_name(right_field.value_type),
        ),
    )
    temporal = contract.temporal_plan
    plan: PhysicalPlan = PhysicalTemporal(
        left_input,
        predicate,
        "CONS" if isinstance(temporal, LogicalConsecutive) else "EXIST",
        temporal.spec.comparator,
        temporal.spec.threshold,
        temporal.spec.maximum,
        temporal.spec.unit,
        temporal.spec.every,
        _lower_temporal_window(temporal.spec.window),
        temporal.spec.trading_sequence,
        (scalar,),
    )
    if contract.limit is not None:
        plan = PhysicalLimit(plan, contract.limit[0], contract.limit[1])
    validate_physical_plan(plan, catalog, expressions)
    decision = PhysicalDecision(
        resource_id=resource_id,
        feasible=True,
        cost=float(catalog.resource(resource_id).priority * 2),
        estimated=statistics is None,
        reason_code="PHYSICAL_TEMPORAL_SCALAR_SELECTED",
        reason="independent aggregate scalar is cross-joined before temporal bucketing",
        strategy_id="temporal_cross_scope_scalar",
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        resource_id,
        (decision,),
        "temporal_cross_scope_scalar",
    )


def _plan_temporal_rank(
    contract: _TemporalRankContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
) -> PhysicalPlanningResult:
    if len(resource_ids) != 1:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_MULTI_RESOURCE_UNSUPPORTED",
            "temporal rank currently requires one physical measure resource",
        )
    selected = resource_ids[0]
    resource = catalog.resource(selected)
    anchor_id = resource.anchor_resource_id or selected
    anchor = catalog.resource(anchor_id)
    if anchor.partition_key is None or not {"mktcode", "tgtcode", "bizdate"}.issubset(anchor.stable_keys):
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_ANCHOR_UNAVAILABLE",
            f"resource {selected} has no dated stable security anchor",
        )
    indicator_id = contract.call.binding.slots.get("indicator_name", "")
    field = _field_for_indicator(fields, indicator_id)
    input_plan: PhysicalPlan = PhysicalScan(
        selected,
        _scan_columns((field,)),
        None,
        resource.anchor_resource_id,
    )
    for constraint in _call_constraints(contract.call, catalog, selected):
        input_plan = PhysicalFilter(input_plan, constraint)
    input_plan = _with_dynamic_prefixes(input_plan, (field,))
    bound, percentage = _rank_bound(
        contract.rank_bound,
        ">=" if contract.rank_comparator == "between" else contract.rank_comparator,
    )
    upper_bound = None
    if contract.rank_upper_bound is not None:
        upper_bound, upper_percentage = _rank_bound(
            contract.rank_upper_bound,
            "<=",
        )
        if upper_percentage != percentage:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_BOUND_UNSUPPORTED",
                "temporal rank range bounds must use the same numeric or percentage unit",
            )
    temporal = contract.temporal_plan
    plan: PhysicalPlan = PhysicalTemporalRank(
        input=input_plan,
        measure=_physical_field_expression(field),
        aggregate_function=contract.aggregate_function,
        direction=contract.direction,
        rank_comparator=contract.rank_comparator,
        rank_bound=bound,
        rank_percentage=percentage,
        mode="CONS" if isinstance(temporal, LogicalConsecutive) else "EXIST",
        comparator=temporal.spec.comparator,
        threshold=temporal.spec.threshold,
        maximum=temporal.spec.maximum,
        unit=temporal.spec.unit,
        every=temporal.spec.every,
        window=_lower_temporal_window(temporal.spec.window),
        anchor_resource_id=anchor_id,
        trading_sequence=temporal.spec.trading_sequence,
        rank_upper_bound=upper_bound,
        rank_lower_inclusive=contract.rank_lower_inclusive,
        rank_upper_inclusive=contract.rank_upper_inclusive,
    )
    if contract.limit is not None:
        plan = PhysicalLimit(plan, contract.limit[0], contract.limit[1])
    validate_physical_plan(plan, catalog, expressions)
    decision = replace(
        _candidate_decision(resource, catalog, statistics),
        strategy_id="temporal_rank",
        selected=True,
    )
    return PhysicalPlanningResult(plan, selected, (decision,), "temporal_rank")


def _plan_temporal_aggregate(
    contract: _TemporalAggregateContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
) -> PhysicalPlanningResult:
    if len(resource_ids) != 1:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_MULTI_RESOURCE_UNSUPPORTED",
            "temporal aggregate currently requires one physical measure resource",
        )
    selected = resource_ids[0]
    resource = catalog.resource(selected)
    anchor_id = resource.anchor_resource_id or selected
    anchor = catalog.resource(anchor_id)
    if anchor.partition_key is None or not {"mktcode", "tgtcode", "bizdate"}.issubset(anchor.stable_keys):
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_ANCHOR_UNAVAILABLE",
            f"resource {selected} has no dated stable security anchor",
        )
    indicator_id = contract.call.binding.slots.get("indicator_name", "")
    field = _field_for_indicator(fields, indicator_id)
    input_plan: PhysicalPlan = PhysicalScan(
        selected,
        _scan_columns((field,)),
        None,
        resource.anchor_resource_id,
    )
    for constraint in _call_constraints(contract.call, catalog, selected):
        input_plan = PhysicalFilter(input_plan, constraint)
    input_plan = _with_dynamic_prefixes(input_plan, (field,))
    temporal = contract.temporal_plan
    plan: PhysicalPlan = PhysicalTemporalAggregate(
        input_plan,
        _physical_field_expression(field),
        contract.function,
        contract.value_comparator,
        _physical_literal(contract.value_bound),
        "CONS" if isinstance(temporal, LogicalConsecutive) else "EXIST",
        temporal.spec.comparator,
        temporal.spec.threshold,
        temporal.spec.maximum,
        temporal.spec.unit,
        temporal.spec.every,
        _lower_temporal_window(temporal.spec.window),
        anchor_id,
        temporal.spec.trading_sequence,
    )
    if contract.limit is not None:
        plan = PhysicalLimit(plan, contract.limit[0], contract.limit[1])
    validate_physical_plan(plan, catalog, expressions)
    decision = replace(
        _candidate_decision(resource, catalog, statistics),
        strategy_id="temporal_grouped_aggregate",
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        selected,
        (decision,),
        "temporal_grouped_aggregate",
    )


def _plan_grouped_aggregate(
    logical_plan,
    contract: _AggregateContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
    strategies: Optional[PhysicalStrategyRegistry],
    allow_shadow_strategies: bool,
) -> PhysicalPlanningResult:
    if len(resource_ids) != 1:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_MULTI_RESOURCE_UNSUPPORTED",
            "grouped aggregate currently requires one measure resource",
        )
    selected = resource_ids[0]
    resource = catalog.resource(selected)
    anchor_id = resource.anchor_resource_id or selected
    anchor = catalog.resource(anchor_id)
    if anchor.partition_key is None or not {"mktcode", "tgtcode", "bizdate"}.issubset(anchor.stable_keys):
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_ANCHOR_UNAVAILABLE",
            f"resource {selected} has no dated stable security anchor",
        )
    scan = PhysicalScan(
        selected,
        _scan_columns(fields),
        None,
        resource.anchor_resource_id,
    )
    input_plan: PhysicalPlan = scan
    for constraint in _call_constraints(contract.call, catalog, selected):
        input_plan = PhysicalFilter(input_plan, constraint)
    indicator_id = contract.call.binding.slots.get("indicator_name", "")
    field = _field_for_indicator(fields, indicator_id)
    input_plan = _with_dynamic_prefixes(input_plan, (field,))
    measure = _physical_field_expression(field)
    bound = _physical_literal(contract.bound)
    plan: PhysicalPlan = PhysicalGroupedAggregate(
        input_plan,
        measure,
        contract.function,
        contract.comparator,
        bound,
        anchor_id,
    )
    if contract.limit is not None:
        plan = PhysicalLimit(plan, contract.limit[0], contract.limit[1])
    validate_physical_plan(plan, catalog, expressions)
    baseline_decision = replace(
        _candidate_decision(resource, catalog, statistics),
        strategy_id="grouped_aggregate",
    )
    candidates = [
        _PlanCandidate(
            plan,
            selected,
            "grouped_aggregate",
            baseline_decision,
            baseline=True,
        )
    ]
    if strategies is not None:
        candidates.extend(
            _grouped_aggregate_candidates(
                contract,
                field,
                catalog,
                statistics,
                strategies,
                expressions,
                allow_shadow_strategies,
            )
        )
    return _select_plan_candidates(candidates)


def _grouped_aggregate_candidates(
    contract: _AggregateContract,
    field: _ResolvedIndicator,
    catalog: PhysicalCatalog,
    statistics: Optional[PhysicalStatisticsSnapshot],
    strategies: PhysicalStrategyRegistry,
    expressions: Optional[PhysicalExpressionRegistry],
    allow_shadow_strategies: bool,
) -> Tuple[_PlanCandidate, ...]:
    typed_date = contract.call.date_constraint
    if typed_date is None:
        date = str(contract.call.binding.slots.get("date", "")).strip()
        typed_date = parse_date_constraint(date) if date else None
    if typed_date is None or typed_date.kind != "recent_sessions" or not typed_date.amount:
        return ()
    function = contract.function.upper()
    candidates = []
    for strategy in strategies.aggregate_strategies_for(field.indicator_id):
        if strategy.scan_resource_id != field.resource_id:
            continue
        if isinstance(strategy, PhysicalPrefixAggregateStrategy):
            if (
                function not in strategy.functions
                or not strategy.min_window <= typed_date.amount <= strategy.max_window
            ):
                continue
            constraints = _aggregate_non_window_constraints(
                contract.call,
                catalog,
                strategy.prefix_resource_id,
            )
            semantic_eligible = _prefix_aggregate_semantically_eligible(
                strategy,
                typed_date.amount,
                statistics,
            )
            as_of_date = _prefix_aggregate_as_of_date(
                strategy,
                statistics,
            ) if semantic_eligible else None
            candidate_plan: PhysicalPlan = PhysicalPrefixAggregate(
                strategy.prefix_resource_id,
                catalog.resource(strategy.prefix_resource_id).anchor_resource_id
                or strategy.scan_resource_id,
                strategy.sum_column,
                strategy.count_column,
                typed_date.amount,
                function,
                contract.comparator,
                _physical_literal(contract.bound),
                strategy.scale_divisor,
                constraints,
                semantic_eligible,
                as_of_date,
            )
            candidate_resource_id = strategy.prefix_resource_id
        elif isinstance(strategy, PhysicalMaterializedAggregateStrategy):
            if function != strategy.function or typed_date.amount != strategy.window:
                continue
            candidate_resource_id = strategy.materialized_resource_id
            feature = PhysicalColumn(
                candidate_resource_id,
                strategy.feature_column,
                NUMERIC,
            )
            measure = feature
            if strategy.scale_divisor != 1.0:
                measure = PhysicalBinary(
                    "/",
                    feature,
                    PhysicalLiteral(strategy.scale_divisor, NUMERIC),
                    NUMERIC,
                )
            candidate_plan = PhysicalScan(
                candidate_resource_id,
                (feature,),
                None,
                None,
            )
            for constraint in _aggregate_non_window_constraints(
                contract.call,
                catalog,
                candidate_resource_id,
            ):
                candidate_plan = PhysicalFilter(candidate_plan, constraint)
            candidate_plan = PhysicalFilter(
                candidate_plan,
                PhysicalComparison(
                    contract.comparator,
                    measure,
                    _physical_literal(contract.bound),
                ),
            )
            candidate_plan = _with_latest_snapshot(
                candidate_plan,
                catalog,
                candidate_resource_id,
            )
            semantic_eligible = False
        else:
            continue
        if contract.limit is not None:
            candidate_plan = PhysicalLimit(
                candidate_plan,
                contract.limit[0],
                contract.limit[1],
            )
        validate_physical_plan(candidate_plan, catalog, expressions)
        decision = _aggregate_strategy_decision(
            strategy,
            catalog,
            statistics,
            allow_shadow_strategies,
            semantic_eligible=semantic_eligible,
        )
        candidates.append(
            _PlanCandidate(
                candidate_plan,
                candidate_resource_id,
                strategy.strategy_id,
                decision,
            )
        )
    return tuple(candidates)


def _aggregate_non_window_constraints(call, catalog, resource_id):
    constraints = tuple(_call_constraints(call, catalog, resource_id))
    recent = tuple(item for item in constraints if isinstance(item, PhysicalRecentSessions))
    if len(recent) != 1:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_WINDOW_UNAVAILABLE",
            "accelerated aggregate requires exactly one recent-session window",
        )
    return tuple(item for item in constraints if not isinstance(item, PhysicalRecentSessions))


def _select_plan_candidates(candidates) -> PhysicalPlanningResult:
    ordered = sorted(
        candidates,
        key=lambda item: (
            not item.decision.selection_eligible,
            float("inf")
            if item.decision.cost is None
            else item.decision.cost * (2.0 if item.decision.estimated else 1.0),
            item.strategy_id,
        ),
    )
    chosen = ordered[0]
    decisions = tuple(
        replace(item.decision, strategy_id=item.strategy_id, selected=item is chosen)
        for item in ordered
    )
    return PhysicalPlanningResult(
        chosen.plan,
        chosen.resource_id,
        decisions,
        chosen.strategy_id,
    )


def _plan_aggregate_rank(
    contract: _AggregateRankContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
) -> PhysicalPlanningResult:
    function = str(contract.call.binding.slots.get("agg_func", "")).strip().lower()
    if function not in {item.lower() for item in _SET_AGGREGATE_FUNCTIONS}:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
            f"aggregate rank function requires a dedicated contract: {function.upper()}",
        )
    indicator_id = contract.call.binding.slots.get("indicator_name", "")
    field = _field_for_indicator(fields, indicator_id)
    resource = catalog.resource(field.resource_id)
    anchor_id = resource.anchor_resource_id or field.resource_id
    anchor = catalog.resource(anchor_id)
    if anchor.partition_key is None or not {"mktcode", "tgtcode", "bizdate"}.issubset(anchor.stable_keys):
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_ANCHOR_UNAVAILABLE",
            f"resource {field.resource_id} has no dated stable security anchor",
        )
    aggregate_input: PhysicalPlan = PhysicalScan(
        field.resource_id,
        _scan_columns((field,)),
        None,
        resource.anchor_resource_id,
    )
    for constraint in _call_constraints(contract.call, catalog, field.resource_id):
        aggregate_input = PhysicalFilter(aggregate_input, constraint)
    aggregate_input = _with_dynamic_prefixes(aggregate_input, (field,))
    bound, percentage, upper_bound = _physical_rank_bounds(
        contract.bound,
        contract.comparator,
        contract.upper_bound,
    )
    plan: PhysicalPlan = PhysicalAggregateRank(
        aggregate_input,
        _physical_field_expression(field),
        function,
        contract.direction,
        bound,
        contract.comparator,
        percentage,
        anchor_id,
        upper_bound,
        contract.lower_inclusive,
        contract.upper_inclusive,
    )
    if contract.limit is not None:
        plan = PhysicalLimit(plan, contract.limit[0], contract.limit[1])
    validate_physical_plan(plan, catalog, expressions)
    decision = replace(
        _candidate_decision(resource, catalog, statistics),
        strategy_id="aggregate_rank",
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        field.resource_id,
        (decision,),
        "aggregate_rank",
    )


def _requires_period_scalar(call: CallExpr) -> bool:
    if call.binding is None:
        return False
    if str(call.binding.slots.get("agg_func", "")).strip() or str(
        call.binding.slots.get("count_exp", "")
    ).strip():
        return False
    date = str(call.binding.slots.get("date", "")).strip()
    if not date:
        return False
    typed_date = call.date_constraint or parse_date_constraint(date)
    return typed_date.kind not in {"relative", "exact", "relative_session"}


def _anchor_external_date_constraint(expression, anchor_resource_id: str):
    if isinstance(expression, PhysicalLatestValue):
        return replace(expression, resource_id=anchor_resource_id)
    if isinstance(expression, PhysicalNthLatestValue):
        return replace(expression, resource_id=anchor_resource_id)
    if isinstance(expression, PhysicalRecentSessions):
        return replace(expression, anchor_resource_id=anchor_resource_id)
    if isinstance(expression, PhysicalDynamicDateRange):
        return replace(expression, anchor_resource_id=anchor_resource_id)
    if isinstance(expression, PhysicalSessionBoundaryRange):
        return replace(expression, anchor_resource_id=anchor_resource_id)
    if isinstance(expression, PhysicalComparison):
        return replace(
            expression,
            left=_anchor_external_date_constraint(
                expression.left, anchor_resource_id
            ),
            right=_anchor_external_date_constraint(
                expression.right, anchor_resource_id
            ),
        )
    if isinstance(expression, PhysicalBinary):
        return replace(
            expression,
            left=_anchor_external_date_constraint(
                expression.left, anchor_resource_id
            ),
            right=_anchor_external_date_constraint(
                expression.right, anchor_resource_id
            ),
        )
    if isinstance(expression, PhysicalNot):
        return replace(
            expression,
            operand=_anchor_external_date_constraint(
                expression.operand, anchor_resource_id
            ),
        )
    return expression


def _external_index_quote_field(indicator_id: str) -> _ResolvedIndicator:
    columns = {
        "涨幅": "pct_change",
        "涨跌幅": "pct_change",
        "最新价": "close",
        "收盘价": "close",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "成交量": "volume",
    }
    try:
        column = columns[str(indicator_id)]
    except KeyError as exc:
        raise PhysicalPlanningError(
            "PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE",
            f"external index quote does not provide indicator {indicator_id}",
        ) from exc
    return _ResolvedIndicator(
        str(indicator_id),
        "external_index_quote",
        "numeric",
        direct_column=column,
    )


def _build_named_scalar_relations(
    calls: Tuple[CallExpr, ...],
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    *,
    alias_prefix: str,
):
    scalars = []
    refs = {}
    resource_ids = set()
    seen = set()
    for call in calls:
        if call.node_id in seen:
            continue
        seen.add(call.node_id)
        if call.binding is None or call.name not in {"indicator", "queryData"}:
            raise PhysicalPlanningError(
                "PHYSICAL_SCALAR_RELATION_UNSUPPORTED",
                "named scalar relation requires a bound indicator or queryData call",
            )
        index_quote = None
        if call.name == "queryData":
            if not isinstance(call.scope_expression, ScopeAtom):
                raise PhysicalPlanningError(
                    "PHYSICAL_QUERYDATA_SCALAR_AMBIGUOUS",
                    "queryData scalar requires one exact security identity",
                )
            resolved_scope = None
            market = str(call.binding.slots.get("market", "")).strip()
            try:
                benchmark = current_benchmark_policy_catalog().resolve(
                    call.scope_expression.name, market
                )
            except KeyError:
                benchmark = None
            if benchmark is not None:
                try:
                    quote = current_external_index_quote_catalog().resolve(
                        benchmark.index_code
                    )
                except KeyError as exc:
                    raise PhysicalPlanningError(
                        "PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE",
                        f"benchmark policy {benchmark.policy_id} selects index "
                        f"{benchmark.index_code} without a versioned quote snapshot",
                    ) from exc
                index_quote = _IndexQuoteBinding(
                    benchmark.index_code, quote.snapshot_id
                )
            else:
                try:
                    resolved_scope = current_security_scope_catalog().resolve(
                        call.scope_expression.name
                    )
                except KeyError as exc:
                    try:
                        external = current_external_scope_catalog().resolve(
                            call.scope_expression.name
                        )
                    except KeyError:
                        detail = "scope is absent from security and external catalogs"
                    else:
                        if external.option.scope_type == "index":
                            try:
                                quote = current_external_index_quote_catalog().resolve(
                                    external.option.scope_code
                                )
                            except KeyError:
                                detail = (
                                    f"index {external.option.scope_code} has membership "
                                    "but no versioned quote snapshot"
                                )
                            else:
                                index_quote = _IndexQuoteBinding(
                                    external.option.scope_code, quote.snapshot_id
                                )
                                detail = ""
                        else:
                            detail = (
                                f"{external.option.scope_type} membership does not provide "
                                "a scalar quote for the scope itself"
                            )
                    if index_quote is None:
                        raise PhysicalPlanningError(
                            "PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE",
                            f"queryData scalar is unavailable for "
                            f"{call.scope_expression.name}: {detail}",
                        ) from exc
            if (
                index_quote is None
                and resolved_scope is not None
                and len(resolved_scope.identities) != 1
            ):
                raise PhysicalPlanningError(
                    "PHYSICAL_QUERYDATA_SCALAR_AMBIGUOUS",
                    "queryData scalar scope resolves to multiple securities",
                )
        indicator_id = call.binding.slots.get("indicator_name", "")
        field = (
            _external_index_quote_field(indicator_id)
            if index_quote is not None
            else _field_for_indicator(fields, indicator_id)
        )
        relation_fields = [field]
        if index_quote is None and _scope_requires_security_join(call.scope_expression):
            relation_fields.append(
                next(
                    item
                    for item in fields
                    if item.indicator_id == "__security_scope_name"
                )
            )
        relation_fields_tuple = tuple(relation_fields)
        relation_resource_ids = tuple(
            sorted({item.resource_id for item in relation_fields_tuple})
        )
        if index_quote is not None:
            scalar_root_id = "external_index_quote"
            scalar_input = PhysicalTableScan(
                scalar_root_id,
                _scan_columns(relation_fields_tuple),
            )
        elif len(relation_resource_ids) == 1:
            scalar_root_id = field.resource_id
            resource = catalog.resource(scalar_root_id)
            scalar_input: PhysicalPlan = PhysicalScan(
                scalar_root_id,
                _scan_columns(relation_fields_tuple),
                None,
                resource.anchor_resource_id,
            )
        else:
            scalar_input, scalar_root_id, _ = _build_join_relation(
                relation_fields_tuple,
                relation_resource_ids,
                catalog,
            )
        date = str(call.binding.slots.get("date", "")).strip()
        collapse_latest = _requires_period_scalar(call)
        if index_quote is not None:
            constraints = list(
                _call_constraints(
                    replace(call, scope_expression=None), catalog, scalar_root_id
                )
            )
            constraints = [
                _anchor_external_date_constraint(constraint, "official_basic")
                for constraint in constraints
            ]
            constraints.extend(
                (
                    PhysicalComparison(
                        "=",
                        PhysicalColumn(scalar_root_id, "index_code", STRING),
                        PhysicalLiteral(index_quote.index_code, STRING),
                    ),
                    PhysicalComparison(
                        "=",
                        PhysicalColumn(scalar_root_id, "snapshot_id", STRING),
                        PhysicalLiteral(index_quote.snapshot_id, STRING),
                    ),
                )
            )
        else:
            constraints = list(_call_constraints(call, catalog, scalar_root_id))
        if not date:
            stable_id = (
                catalog.resource(scalar_root_id).anchor_resource_id
                or scalar_root_id
            )
            partition_key = catalog.resource(stable_id).partition_key
            latest_resource_id = (
                "official_basic" if index_quote is not None else stable_id
            )
            constraints.append(
                PhysicalComparison(
                    "=",
                    PhysicalColumn(stable_id, partition_key, TIME),
                    PhysicalLatestValue(
                        latest_resource_id,
                        catalog.resource(latest_resource_id).partition_key,
                        TIME,
                    ),
                )
            )
        for constraint in constraints:
            scalar_input = PhysicalFilter(scalar_input, constraint)
        if index_quote is None:
            scalar_input = _with_dynamic_prefixes(
                scalar_input,
                relation_fields_tuple,
            )
        index = len(scalars)
        relation_alias = f"{alias_prefix}_{index}"
        value_alias = f"{alias_prefix}_value_{index}"
        group_by_security = call.name == "indicator"
        scalars.append(
            PhysicalNamedScalar(
                relation_alias,
                scalar_input,
                _physical_field_expression(field),
                value_alias,
                group_by_security,
                collapse_latest,
            )
        )
        refs[call.node_id] = PhysicalAggregateRef(
            relation_alias,
            value_alias,
            _type_from_name(field.value_type),
        )
        resource_ids.update(relation_resource_ids)
    return tuple(scalars), refs, resource_ids


def _plan_composite_aggregate(
    logical_plan,
    aggregate_calls: Tuple[CallExpr, ...],
    querydata_scalar_calls: Tuple[CallExpr, ...],
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
) -> PhysicalPlanningResult:
    all_calls = tuple(
        call
        for expression in _logical_expressions(logical_plan)
        for call in _walk_calls(expression)
    )
    if any(call.name == "rank" for call in all_calls):
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
            "rank over or beside aggregate measures requires a named window stage",
        )
    predicate, limit = _composite_filter_contract(logical_plan)
    unique_aggregates = []
    seen_aggregates = set()
    for call in aggregate_calls:
        if call.node_id in seen_aggregates:
            continue
        seen_aggregates.add(call.node_id)
        unique_aggregates.append(call)

    refs = {}
    groups = []
    scalars = []
    aggregate_resource_ids = set()
    for index, call in enumerate(unique_aggregates):
        function = str(call.binding.slots.get("agg_func", "")).strip().lower()
        if call.name == "belong_industry" and not function:
            function = "avg"
        if function not in {item.lower() for item in _SET_AGGREGATE_FUNCTIONS}:
            raise PhysicalPlanningError(
                "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
                f"aggregate function requires a dedicated contract: {function.upper()}",
            )
        indicator_id = call.binding.slots.get("indicator_name", "")
        field = _field_for_indicator(fields, indicator_id)
        aggregate_resource_ids.add(field.resource_id)
        aggregate_fields = [field]
        if _scope_requires_security_join(call.scope_expression):
            aggregate_fields.append(
                next(item for item in fields if item.indicator_id == "__security_scope_name")
            )
        aggregate_resource_ids_for_call = tuple(
            sorted({item.resource_id for item in aggregate_fields})
        )
        if len(aggregate_resource_ids_for_call) == 1:
            aggregate_root_id = field.resource_id
            resource = catalog.resource(aggregate_root_id)
            aggregate_input = PhysicalScan(
                aggregate_root_id,
                _scan_columns(tuple(aggregate_fields)),
                None,
                resource.anchor_resource_id,
            )
        else:
            aggregate_input, aggregate_root_id, _ = _build_join_relation(
                tuple(aggregate_fields),
                aggregate_resource_ids_for_call,
                catalog,
            )
        aggregate_resource_ids.update(aggregate_resource_ids_for_call)
        aggregate_constraints = list(
            _call_constraints(call, catalog, aggregate_root_id)
        )
        if (
            call.name == "belong_industry"
            and not str(call.binding.slots.get("date", "")).strip()
        ):
            stable_id = (
                catalog.resource(aggregate_root_id).anchor_resource_id
                or aggregate_root_id
            )
            partition_key = catalog.resource(stable_id).partition_key
            aggregate_constraints.append(
                PhysicalComparison(
                    "=",
                    PhysicalColumn(stable_id, partition_key, TIME),
                    PhysicalLatestValue(stable_id, partition_key, TIME),
                )
            )
        for constraint in aggregate_constraints:
            aggregate_input = PhysicalFilter(aggregate_input, constraint)
        aggregate_input = _with_dynamic_prefixes(
            aggregate_input,
            tuple(aggregate_fields),
        )
        relation_alias = f"aggregate_{index}"
        measure_alias = f"metric_{index}"
        measure = PhysicalNamedAggregate(
            measure_alias,
            function,
            _physical_field_expression(field),
        )
        industry_policy = (
            current_external_data_policy().industry
            if call.name == "belong_industry"
            else None
        )
        if call.name == "belong_industry" and industry_policy is None:
            raise PhysicalPlanningError(
                "PHYSICAL_INDUSTRY_DATA_UNAVAILABLE",
                "belong_industry requires a versioned industry membership dataset",
            )
        groups.append(
            PhysicalAggregateGroup(
                relation_alias,
                aggregate_input,
                (measure,),
                group_by_security=call.name != "queryData",
                industry_membership_resource_id=(
                    industry_policy.resource_id if industry_policy else None
                ),
                industry_snapshot_id=(
                    industry_policy.snapshot_id if industry_policy else None
                ),
                industry_classification_system=(
                    industry_policy.classification_system if industry_policy else None
                ),
                industry_level=(
                    industry_policy.industry_level if industry_policy else None
                ),
            )
        )
        refs[call.node_id] = PhysicalAggregateRef(
            relation_alias,
            measure_alias,
            _type_from_name(field.value_type),
        )

    aggregate_ids = {call.node_id for call in unique_aggregates}
    period_indicator_calls = tuple(
        call
        for call in all_calls
        if call.node_id not in aggregate_ids
        and call.name == "indicator"
        and _requires_period_scalar(call)
    )
    period_indicator_ids = {call.node_id for call in period_indicator_calls}
    singleton_indicator_calls = tuple(
        call
        for call in all_calls
        if call.node_id not in aggregate_ids | period_indicator_ids
        and call.name == "indicator"
        and call.binding is not None
        and str(call.binding.slots.get("date", "")).strip()
        and (call.date_constraint or parse_date_constraint(
            str(call.binding.slots.get("date", ""))
        )).kind in {"relative", "exact", "relative_session"}
    )
    singleton_signatures = {
        (call.date_constraint or parse_date_constraint(
            str(call.binding.slots.get("date", ""))
        )).canonical_json()
        for call in singleton_indicator_calls
    }
    independent_singletons = (
        singleton_indicator_calls if len(singleton_signatures) > 1 else ()
    )
    named_scalar_calls = (
        tuple(querydata_scalar_calls)
        + period_indicator_calls
        + independent_singletons
    )
    (
        named_scalars,
        scalar_refs,
        scalar_resource_ids,
    ) = _build_named_scalar_relations(
        named_scalar_calls,
        catalog,
        fields,
        alias_prefix="scalar",
    )
    scalars.extend(named_scalars)
    refs.update(scalar_refs)
    aggregate_resource_ids.update(scalar_resource_ids)

    named_relation_ids = seen_aggregates | {
        call.node_id for call in named_scalar_calls
    }
    scalar_calls = tuple(
        call for call in all_calls if call.node_id not in named_relation_ids
    )
    scalar_fields = []
    for call in scalar_calls:
        if call.name not in _DIRECT_FIELD_CALLS or call.binding is None:
            raise PhysicalPlanningError(
                "PHYSICAL_EXPRESSION_UNSUPPORTED",
                f"unsupported scalar call beside aggregate measure: {call.name}",
            )
        indicator_id = call.binding.slots.get("indicator_name", "")
        scalar_fields.append(_field_for_indicator(fields, indicator_id))
    scalar_fields = tuple(
        {field.indicator_id.casefold(): field for field in scalar_fields}.values()
    )
    anchor_input, anchor_resource_id, allowed_resource_ids = _composite_anchor_relation(
        scalar_fields,
        scalar_calls,
        catalog,
    )
    physical_predicate = _lower_composite_expr(
        predicate,
        catalog,
        anchor_resource_id,
        fields,
        refs,
        frozenset(allowed_resource_ids),
    )
    plan: PhysicalPlan = PhysicalCompositeAggregate(
        anchor_input,
        tuple(groups),
        tuple(scalars),
        physical_predicate,
        "official_basic",
    )
    if limit is not None:
        plan = PhysicalLimit(plan, limit[0], limit[1])
    validate_physical_plan(plan, catalog, expressions)
    resources = sorted(aggregate_resource_ids | set(allowed_resource_ids))
    selected_resource = "+".join(resources)
    cost = sum(catalog.resource(item).priority for item in resources)
    decision = PhysicalDecision(
        resource_id=selected_resource,
        feasible=True,
        cost=float(cost),
        estimated=True,
        reason_code="PHYSICAL_NAMED_AGGREGATE_SELECTED",
        reason="independent grouped measure relations joined on catalog stable security keys",
        strategy_id="composite_grouped_aggregate",
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        selected_resource,
        (decision,),
        "composite_grouped_aggregate",
    )


def _plan_rank_expression(
    lowering: LoweringResult,
    contract: _RankExpressionContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
    strategies: Optional[PhysicalStrategyRegistry],
    allow_shadow_strategies: bool,
) -> PhysicalPlanningResult:
    unique_calls = []
    seen = set()
    for call in contract.calls:
        if call.node_id not in seen:
            seen.add(call.node_id)
            unique_calls.append(call)

    refs = {}
    ranks = []
    rank_resources = set()
    for index, call in enumerate(unique_calls):
        if call.binding is None:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
                "rank expression contains an unbound rank call",
            )
        direction = str(call.binding.slots.get("direction", "")).strip().lower()
        if direction not in {"asc", "desc"}:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_DIRECTION_UNSUPPORTED",
                f"unsupported rank direction: {direction}",
            )
        function = str(call.binding.slots.get("agg_func", "")).strip().upper() or None
        if function is not None and function not in _SET_AGGREGATE_FUNCTIONS:
            raise PhysicalPlanningError(
                "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
                f"rank expression aggregate requires a dedicated contract: {function}",
            )
        indicator_id = call.binding.slots.get("indicator_name", "")
        field = _field_for_indicator(fields, indicator_id)
        resource = catalog.resource(field.resource_id)
        rank_resources.add(field.resource_id)
        rank_input: PhysicalPlan = PhysicalScan(
            field.resource_id,
            _scan_columns((field,)),
            None,
            resource.anchor_resource_id,
        )
        constraints = list(_call_constraints(call, catalog, field.resource_id))
        date = str(call.binding.slots.get("date", "")).strip()
        collapse_latest = False
        if not date and function is None:
            stable_id = resource.anchor_resource_id or field.resource_id
            partition_key = catalog.resource(stable_id).partition_key
            constraints.append(
                PhysicalComparison(
                    "=",
                    PhysicalColumn(stable_id, partition_key, TIME),
                    PhysicalLatestValue(stable_id, partition_key, TIME),
                )
            )
        elif date and function is None:
            typed_date = call.date_constraint or parse_date_constraint(date)
            collapse_latest = typed_date.kind not in {
                "relative",
                "exact",
                "relative_session",
            }
        for constraint in constraints:
            rank_input = PhysicalFilter(rank_input, constraint)
        relation_alias = f"rank_{index}"
        value_alias = f"rank_value_{index}"
        ranks.append(
            PhysicalNamedRank(
                relation_alias,
                rank_input,
                _physical_field_expression(field),
                direction,
                value_alias,
                function.lower() if function else None,
                collapse_latest,
            )
        )
        refs[call.node_id] = PhysicalAggregateRef(
            relation_alias,
            value_alias,
            NUMERIC,
        )

    all_calls = tuple(_walk_calls(contract.predicate))
    scalar_calls = tuple(call for call in all_calls if call.node_id not in seen)
    period_scalar_calls = tuple(
        call
        for call in scalar_calls
        if call.name in {"indicator", "queryData"}
        and _requires_period_scalar(call)
    )
    period_scalars, scalar_refs, scalar_resources = _build_named_scalar_relations(
        period_scalar_calls,
        catalog,
        fields,
        alias_prefix="rank_scalar",
    )
    refs.update(scalar_refs)
    rank_resources.update(scalar_resources)
    period_scalar_ids = {call.node_id for call in period_scalar_calls}
    scalar_calls = tuple(
        call for call in scalar_calls if call.node_id not in period_scalar_ids
    )
    if isinstance(contract.input_plan, LogicalDomainScan):
        scalar_fields = tuple(
            {
                call.binding.slots.get("indicator_name", "").casefold(): _field_for_indicator(
                    fields,
                    call.binding.slots.get("indicator_name", ""),
                )
                for call in scalar_calls
                if call.name in _DIRECT_FIELD_CALLS and call.binding is not None
            }.values()
        )
        anchor_input, anchor_resource_id, allowed_resource_ids = _composite_anchor_relation(
            scalar_fields,
            scalar_calls,
            catalog,
        )
        anchor_decisions = ()
    else:
        if scalar_calls:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
                "stage rank expressions cannot mix new scalar projections before named stage projection",
            )
        anchor_result = plan_physical(
            replace(lowering, plan=contract.input_plan),
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=allow_shadow_strategies,
        )
        anchor_input = anchor_result.plan
        anchor_resource_id = "official_basic"
        allowed_resource_ids = ("official_basic",)
        anchor_decisions = anchor_result.decisions

    predicate = _lower_composite_expr(
        contract.predicate,
        catalog,
        anchor_resource_id,
        fields,
        refs,
        frozenset(allowed_resource_ids),
    )
    plan: PhysicalPlan = PhysicalRankExpression(
        anchor_input,
        tuple(ranks),
        predicate,
        "official_basic",
        period_scalars,
    )
    if contract.limit is not None:
        plan = PhysicalLimit(plan, contract.limit[0], contract.limit[1])
    validate_physical_plan(plan, catalog, expressions)
    selected = "+".join(sorted(rank_resources | set(allowed_resource_ids)))
    decision = PhysicalDecision(
        resource_id=selected,
        feasible=True,
        cost=float(sum(catalog.resource(item).priority for item in rank_resources)),
        estimated=True,
        reason_code="PHYSICAL_NAMED_RANK_SELECTED",
        reason="independent rank relations joined on stable security keys",
        strategy_id="named_rank_expression",
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        selected,
        (*anchor_decisions, decision),
        "named_rank_expression",
    )


def _composite_filter_contract(plan):
    limit = None
    current = plan
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, LogicalFilter):
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_COMPOSITION_UNSUPPORTED",
            "composite aggregate requires one boolean filter relation",
        )
    return current.predicate, limit


def _physical_field_expression(field: _ResolvedIndicator):
    if field.indicator_id == "稳定证券顺序":
        return PhysicalLiteral(0, NUMERIC)
    if field.indicator_id == "是否T+0":
        policy = current_external_data_policy().instrument_rule
        if policy is None:
            raise PhysicalPlanningError(
                "PHYSICAL_INSTRUMENT_RULE_DATA_UNAVAILABLE",
                "T+0 screening requires a versioned instrument rule dataset",
            )
        return PhysicalExternalExists(
            policy.resource_id,
            "official_basic",
            (
                ("snapshot_id", PhysicalLiteral(policy.snapshot_id, STRING)),
                ("t0_eligible", PhysicalLiteral(True, BOOLEAN)),
            ),
        )
    if field.prefix_average is not None:
        return PhysicalPrefixRef(_dynamic_prefix_alias(field), NUMERIC)
    if field.direct_column is not None:
        return PhysicalColumn(
            field.resource_id,
            field.direct_column,
            _type_from_name(field.value_type),
        )
    assert field.expression is not None
    return _lower_declared_expression(field.expression, field.resource_id)


def _composite_anchor_relation(
    scalar_fields: Tuple[_ResolvedIndicator, ...],
    scalar_calls: Tuple[CallExpr, ...],
    catalog: PhysicalCatalog,
):
    dated = []
    for call in scalar_calls:
        date = str(call.binding.slots.get("date", "")).strip()
        if not date:
            continue
        typed_date = call.date_constraint or parse_date_constraint(date)
        if typed_date.kind not in {"relative", "exact", "relative_session"}:
            raise PhysicalPlanningError(
                "PHYSICAL_SCALAR_SCOPE_UNBOUNDED",
                f"scalar value beside aggregate requires a singleton date, got {date}",
            )
        dated.append(typed_date)
    signatures = {item.canonical_json() for item in dated}
    if len(signatures) > 1:
        raise PhysicalPlanningError(
            "PHYSICAL_SCALAR_SCOPE_MISMATCH",
            "scalar values beside aggregate measures must share one snapshot date",
        )

    resource_ids = tuple(sorted({field.resource_id for field in scalar_fields}))
    if not resource_ids:
        root_id = "official_basic"
        relation: PhysicalPlan = PhysicalScan(root_id, (), None, None)
        allowed = (root_id,)
    elif len(resource_ids) == 1:
        root_id = resource_ids[0]
        resource = catalog.resource(root_id)
        relation = PhysicalScan(
            root_id,
            _scan_columns(scalar_fields),
            None,
            resource.anchor_resource_id,
        )
        allowed = (root_id,)
    else:
        relation, root_id, allowed = _build_join_relation(
            scalar_fields,
            resource_ids,
            catalog,
        )

    constraints = []
    for call in scalar_calls:
        constraints.extend(_call_constraints(call, catalog, root_id))
    if not dated:
        stable_id = catalog.resource(root_id).anchor_resource_id or root_id
        partition_key = catalog.resource(stable_id).partition_key
        constraints.append(
            PhysicalComparison(
                "=",
                PhysicalColumn(stable_id, partition_key, TIME),
                PhysicalLatestValue(stable_id, partition_key, TIME),
            )
        )
    if constraints:
        combined = constraints[0]
        for constraint in constraints[1:]:
            combined = PhysicalBinary("and", combined, constraint, BOOLEAN)
        relation = PhysicalFilter(relation, _deduplicate_and(combined))
    relation = _with_dynamic_prefixes(relation, scalar_fields)
    return relation, root_id, allowed


def _lower_composite_expr(
    expression,
    catalog,
    resource_id,
    fields,
    refs,
    allowed_resource_ids,
):
    if isinstance(expression, LiteralExpr):
        return _physical_literal(expression)
    if isinstance(expression, CallExpr):
        if expression.node_id in refs:
            return refs[expression.node_id]
        if _configured_function_signature(expression) is not None:
            return _lower_configured_function(
                expression,
                lambda item: _lower_composite_expr(
                    item,
                    catalog,
                    resource_id,
                    fields,
                    refs,
                    allowed_resource_ids,
                ),
            )
        if expression.name not in _DIRECT_FIELD_CALLS or expression.binding is None:
            raise PhysicalPlanningError(
                "PHYSICAL_EXPRESSION_UNSUPPORTED",
                f"unsupported physical call {expression.name}",
            )
        indicator_id = expression.binding.slots.get("indicator_name", "")
        field = _field_for_indicator(fields, indicator_id)
        if field.resource_id not in allowed_resource_ids:
            raise PhysicalPlanningError(
                "PHYSICAL_MULTI_RESOURCE_UNSUPPORTED",
                "scalar aggregate expression references an unavailable anchor resource",
            )
        return _physical_field_expression(field)
    if isinstance(expression, BinaryExpr):
        left = _lower_composite_expr(expression.left, catalog, resource_id, fields, refs, allowed_resource_ids)
        right = _lower_composite_expr(expression.right, catalog, resource_id, fields, refs, allowed_resource_ids)
        if expression.op == "/":
            right = PhysicalNullIf(right, PhysicalLiteral(0, right.type), right.type)
        return PhysicalBinary(expression.op, left, right, expression.type)
    if isinstance(expression, ComparisonExpr):
        if expression.op == "~=":
            return _lower_approximate_comparison(
                _lower_composite_expr(expression.left, catalog, resource_id, fields, refs, allowed_resource_ids),
                _lower_composite_expr(expression.right, catalog, resource_id, fields, refs, allowed_resource_ids),
            )
        if isinstance(expression.right, RangeExpr) and expression.op == "between":
            value = _lower_composite_expr(expression.left, catalog, resource_id, fields, refs, allowed_resource_ids)
            lower = _lower_composite_expr(expression.right.lower, catalog, resource_id, fields, refs, allowed_resource_ids)
            upper = _lower_composite_expr(expression.right.upper, catalog, resource_id, fields, refs, allowed_resource_ids)
            return PhysicalBinary(
                "and",
                PhysicalComparison(">=" if expression.right.lower_inclusive else ">", value, lower),
                PhysicalComparison("<=" if expression.right.upper_inclusive else "<", value, upper),
                BOOLEAN,
            )
        return PhysicalComparison(
            expression.op,
            _lower_composite_expr(expression.left, catalog, resource_id, fields, refs, allowed_resource_ids),
            _lower_composite_expr(expression.right, catalog, resource_id, fields, refs, allowed_resource_ids),
        )
    raise PhysicalPlanningError(
        "PHYSICAL_EXPRESSION_UNSUPPORTED",
        f"unsupported composite aggregate expression {type(expression).__name__}",
    )


def _plan_multi_resource(
    lowering: LoweringResult,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
) -> PhysicalPlanningResult:
    temporal = _contains_temporal_plan(lowering.plan)
    relation, root_id, joined = _build_join_relation(fields, resource_ids, catalog)
    plan = _lower_plan(
        lowering.plan,
        catalog,
        root_id,
        fields,
        base_plan=relation,
        allowed_resource_ids=frozenset(joined),
    )
    plan = _with_dynamic_prefixes(plan, fields)
    if _needs_implicit_latest_snapshot(lowering.plan):
        plan = _with_latest_snapshot(plan, catalog, root_id)
    validate_physical_plan(plan, catalog, expressions)
    selected_resource = "+".join(joined)
    strategy_id = "stable_temporal_join" if temporal else "stable_key_join"
    decision = PhysicalDecision(
        resource_id=selected_resource,
        feasible=True,
        cost=float(sum(catalog.resource(item).priority for item in joined)),
        estimated=True,
        reason_code=(
            "PHYSICAL_TEMPORAL_JOIN_SELECTED"
            if temporal
            else "PHYSICAL_STABLE_JOIN_SELECTED"
        ),
        reason=(
            "temporal predicate over a same-entity join on security and trading-date keys"
            if temporal
            else "left-deep same-entity join on catalog-declared stable keys"
        ),
        strategy_id=strategy_id,
        selected=True,
    )
    return PhysicalPlanningResult(plan, selected_resource, (decision,), strategy_id)


def _needs_implicit_latest_snapshot(plan) -> bool:
    current = plan.input if isinstance(plan, LogicalLimit) else plan
    if not isinstance(current, LogicalFilter):
        return False
    calls = tuple(_walk_calls(current.predicate))
    return bool(calls) and all(
        call.binding is not None
        and not str(call.binding.slots.get("date", "")).strip()
        for call in calls
    )


def _with_latest_snapshot(
    plan: PhysicalPlan,
    catalog: PhysicalCatalog,
    resource_id: str,
) -> PhysicalPlan:
    resource = catalog.resource(resource_id)
    stable_id = resource.anchor_resource_id or resource_id
    stable = catalog.resource(stable_id)
    predicate = PhysicalComparison(
        "=",
        PhysicalColumn(stable_id, stable.partition_key, TIME),
        PhysicalLatestValue(stable_id, stable.partition_key, TIME),
    )
    return _with_partition_predicate(plan, stable_id, predicate)


def _with_partition_predicate(
    plan: PhysicalPlan,
    resource_id: str,
    predicate,
) -> PhysicalPlan:
    if isinstance(plan, PhysicalScan):
        combined = (
            predicate
            if plan.partition_predicate is None
            else PhysicalBinary(
                "and",
                plan.partition_predicate,
                predicate,
                BOOLEAN,
            )
        )
        return replace(plan, partition_predicate=combined)
    if isinstance(plan, PhysicalTableScan):
        if plan.resource_id != resource_id:
            return plan
        combined = (
            predicate
            if plan.partition_predicate is None
            else PhysicalBinary(
                "and",
                plan.partition_predicate,
                predicate,
                BOOLEAN,
            )
        )
        return replace(plan, partition_predicate=combined)
    if isinstance(plan, PhysicalJoin):
        return replace(
            plan,
            left=_with_partition_predicate(plan.left, resource_id, predicate),
            right=_with_partition_predicate(plan.right, resource_id, predicate),
        )
    if isinstance(plan, PhysicalPrefixJoin):
        return replace(
            plan,
            input=_with_partition_predicate(plan.input, resource_id, predicate),
        )
    if isinstance(plan, (PhysicalFilter, PhysicalLimit)):
        return replace(
            plan,
            input=_with_partition_predicate(plan.input, resource_id, predicate),
        )
    return plan


def _crossing_calls(plan) -> Tuple[CallExpr, ...]:
    return tuple(
        call
        for expression in _logical_expressions(plan)
        for call in _walk_calls(expression)
        if call.name in _WINDOW_EVENT_CALLS
    )


def _event_composition_contract(plan):
    current = plan
    limit = None
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, LogicalFilter):
        return None
    predicate = current.predicate
    if not isinstance(predicate, BinaryExpr) or predicate.op not in {
        "and",
        "or",
        "&",
        "|",
    }:
        return None
    logical_op = "and" if predicate.op in {"and", "&"} else "or"
    terms = _flatten_boolean_terms(predicate, logical_op)
    event_terms = tuple(term for term in terms if _contains_window_event_call(term))
    other_terms = tuple(term for term in terms if not _contains_window_event_call(term))
    if not event_terms:
        return None
    event_groups = {}
    for term in event_terms:
        signature = tuple(
            sorted(
                {
                    _call_date_signature(call)
                    for call in _walk_calls(term)
                    if call.name in _WINDOW_EVENT_CALLS
                }
            )
        )
        event_groups.setdefault(signature, []).append(term)
    if len(event_groups) > 1:
        first_signature = next(iter(event_groups))
        selected = tuple(event_groups[first_signature])
        remaining = tuple(term for term in terms if term not in selected)
        return (
            current.input,
            _combine_boolean_terms(selected, logical_op),
            _combine_boolean_terms(remaining, logical_op),
            "intersect" if logical_op == "and" else "union",
            limit,
        )
    if not other_terms:
        return None
    event_calls = tuple(
        call for term in event_terms for call in _walk_calls(term)
    )
    other_calls = tuple(
        call for term in other_terms for call in _walk_calls(term)
    )
    projection_compatible = all(
        call.name == "indicator"
        and not str(call.binding.slots.get("agg_func", "")).strip()
        and not str(call.binding.slots.get("count_exp", "")).strip()
        for call in other_calls
    )
    date_scopes = {
        _call_date_signature(call) for call in (*event_calls, *other_calls)
    }
    if projection_compatible and len(date_scopes) <= 1:
        return None
    return (
        current.input,
        _combine_boolean_terms(event_terms, logical_op),
        _combine_boolean_terms(other_terms, logical_op),
        "intersect" if logical_op == "and" else "union",
        limit,
    )


def _call_date_signature(call: CallExpr) -> str:
    date = str(call.binding.slots.get("date", "")).strip()
    if not date:
        return "latest_session"
    constraint = call.date_constraint or parse_date_constraint(date)
    if constraint.kind == "relative" and constraint.anchor == "today":
        return "latest_session"
    return constraint.node_id


def _flatten_boolean_terms(expression, logical_op: str):
    matching_ops = {"and", "&"} if logical_op == "and" else {"or", "|"}
    if isinstance(expression, BinaryExpr) and expression.op in matching_ops:
        return (
            *_flatten_boolean_terms(expression.left, logical_op),
            *_flatten_boolean_terms(expression.right, logical_op),
        )
    return (expression,)


def _combine_boolean_terms(terms, logical_op: str):
    result = terms[0]
    for term in terms[1:]:
        result = BinaryExpr(logical_op, result, term, BOOLEAN)
    return result


def _contains_window_event_call(expression) -> bool:
    return any(call.name in _WINDOW_EVENT_CALLS for call in _walk_calls(expression))


def _normalize_direct_event_absence(expression):
    if not isinstance(expression, ComparisonExpr) or expression.op not in {"=", "!="}:
        return expression, False
    pairs = ((expression.left, expression.right), (expression.right, expression.left))
    for call, literal in pairs:
        if (
            isinstance(call, CallExpr)
            and call.name in (_WINDOW_EVENT_CALLS - _POSITION_CALLS)
            and isinstance(literal, LiteralExpr)
            and isinstance(literal.value, bool)
        ):
            desired = literal.value if expression.op == "=" else not literal.value
            if not desired:
                return (
                    ComparisonExpr(
                        "=",
                        call,
                        LiteralExpr(True, BOOLEAN),
                        BOOLEAN,
                    ),
                    True,
                )
    return expression, False


def _plan_crossing_events(
    lowering: LoweringResult,
    calls: Tuple[CallExpr, ...],
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    *,
    default_latest: bool = True,
) -> PhysicalPlanningResult:
    current = lowering.plan
    limit = None
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, LogicalFilter):
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_PLAN_UNSUPPORTED",
            "crossing events currently require one filter stage",
        )
    event_predicate, event_absence = _normalize_direct_event_absence(
        current.predicate
    )
    all_calls = tuple(_walk_calls(event_predicate))
    if any(call.name not in _WINDOW_EVENT_CALLS | {"indicator"} for call in all_calls):
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED",
            "window events support only direct scalar indicator projections",
        )
    scalar_calls = tuple(call for call in all_calls if call.name == "indicator")
    ignored_event_slots = {
        slot
        for call in calls
        for slot in ("select_type", "agg_func", "count_exp")
        if str(call.binding.slots.get(slot, "")).strip()
    }
    if ignored_event_slots:
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED",
            "window event plan cannot ignore non-empty slots: "
            + ", ".join(sorted(ignored_event_slots)),
        )
    if any(
        str(call.binding.slots.get("agg_func", "")).strip()
        or str(call.binding.slots.get("count_exp", "")).strip()
        for call in scalar_calls
    ):
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED",
            "window events cannot yet mix with aggregate or temporal scalar projections",
        )
    date_scopes = {
        str(call.binding.slots.get("date", "")).strip()
        for call in all_calls
        if str(call.binding.slots.get("date", "")).strip()
    }
    if len(date_scopes) > 1:
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_DATE_SCOPE_MISMATCH",
            "window event composition requires one shared non-empty date scope",
        )
    if len(resource_ids) > 1:
        relation, root_id, joined = _build_join_relation(fields, resource_ids, catalog)
    else:
        selected = resource_ids[0]
        resource = catalog.resource(selected)
        root_id = resource.anchor_resource_id or selected
        relation = PhysicalScan(
            selected,
            _scan_columns(fields),
            None,
            resource.anchor_resource_id,
        )
        joined = (root_id, selected) if root_id != selected else (selected,)

    fixed_period_starts = tuple(
        _parse_fixed_event_period_start(call.binding.slots.get("period", ""))
        for call in calls
    )
    calendar_periods = tuple(
        _parse_calendar_event_period(call.binding.slots.get("period", ""))
        for call in calls
    )
    if any(calendar_periods):
        if not all(calendar_periods) or len(set(calendar_periods)) != 1:
            raise PhysicalPlanningError(
                "PHYSICAL_EVENT_PERIOD_MISMATCH",
                "calendar event composition requires one shared month range",
            )
        stable_resource_id = catalog.resource(root_id).anchor_resource_id or root_id
        start_month, end_month = calendar_periods[0]
        relation = PhysicalFilter(
            relation,
            PhysicalDynamicDateRange(
                stable_resource_id,
                catalog.resource(stable_resource_id).partition_key,
                "year_month_range",
                "month",
                month=start_month,
                end_month=end_month,
            ),
        )
    if any(fixed_period_starts):
        if not all(fixed_period_starts) or len(set(fixed_period_starts)) != 1:
            raise PhysicalPlanningError(
                "PHYSICAL_EVENT_PERIOD_MISMATCH",
                "fixed-start event composition requires one shared period boundary",
            )
        stable_resource_id = catalog.resource(root_id).anchor_resource_id or root_id
        relation = PhysicalFilter(
            relation,
            PhysicalComparison(
                ">=",
                PhysicalColumn(
                    stable_resource_id,
                    catalog.resource(stable_resource_id).partition_key,
                    TIME,
                ),
                PhysicalLiteral(fixed_period_starts[0], TIME),
            ),
        )

    relation = _with_dynamic_prefixes(relation, fields)

    event_defs = []
    event_refs = {}
    projections = []
    projected_refs = {}
    constraints = []
    seen_constraints = set()
    pattern_config = current_physical_pattern_config()
    for index, call in enumerate(calls):
        alias = f"event_{index}"
        if call.name in _CROSSING_CALLS | _PATTERN_CALLS:
            left_id = str(call.binding.slots.get("indicator_name_1", ""))
            right_id = str(call.binding.slots.get("indicator_name_2", ""))
            left = _lower_resolved_indicator(_field_for_indicator(fields, left_id))
            right = _lower_resolved_indicator(_field_for_indicator(fields, right_id))
            if left.type is not NUMERIC or right.type is not NUMERIC:
                raise PhysicalPlanningError(
                    "PHYSICAL_EVENT_TYPE_UNSUPPORTED",
                    "crossing events require two numeric indicators",
                )
            if call.name in _CROSSING_CALLS:
                direction = "below" if call.name == "cross_down" else "above"
                event_defs.append(PhysicalCrossing(alias, left, right, direction))
            else:
                difference = PhysicalAbs(
                    PhysicalBinary("-", left, right, NUMERIC),
                    NUMERIC,
                )
                if call.name == "close_together":
                    denominator = PhysicalNullIf(
                        PhysicalGreatest(
                            (
                                PhysicalAbs(left, NUMERIC),
                                PhysicalAbs(right, NUMERIC),
                            ),
                            NUMERIC,
                        ),
                        PhysicalLiteral(0, NUMERIC),
                        NUMERIC,
                    )
                    predicate = PhysicalComparison(
                        "<=",
                        PhysicalBinary("/", difference, denominator, NUMERIC),
                        PhysicalLiteral(
                            pattern_config.close_together_relative_threshold,
                            NUMERIC,
                        ),
                    )
                else:
                    denominator = PhysicalNullIf(
                        PhysicalAbs(right, NUMERIC),
                        PhysicalLiteral(0, NUMERIC),
                        NUMERIC,
                    )
                    near = PhysicalComparison(
                        "<=",
                        PhysicalBinary("/", difference, denominator, NUMERIC),
                        PhysicalLiteral(
                            pattern_config.reset_near_line_threshold,
                            NUMERIC,
                        ),
                    )
                    floor = PhysicalComparison(
                        ">=",
                        left,
                        PhysicalBinary(
                            "*",
                            right,
                            PhysicalLiteral(
                                1.0 - pattern_config.reset_below_line_tolerance,
                                NUMERIC,
                            ),
                            NUMERIC,
                        ),
                    )
                    predicate = PhysicalBinary("and", near, floor, BOOLEAN)
                event_defs.append(PhysicalPattern(alias, predicate, call.name))
        elif call.name in _EXTREME_CALLS:
            indicator_id = str(call.binding.slots.get("indicator_name", ""))
            value = _lower_resolved_indicator(_field_for_indicator(fields, indicator_id))
            if value.type is not NUMERIC:
                raise PhysicalPlanningError(
                    "PHYSICAL_EVENT_TYPE_UNSUPPORTED",
                    "record extrema require a numeric indicator",
                )
            event_defs.append(
                PhysicalExtreme(
                    alias,
                    value,
                    "high" if call.name == "record_high" else "low",
                    _parse_extreme_lookback(call.binding.slots.get("period", "")),
                )
            )
        else:
            indicator_id = str(call.binding.slots.get("indicator_name", ""))
            value = _lower_resolved_indicator(_field_for_indicator(fields, indicator_id))
            if value.type is not NUMERIC:
                raise PhysicalPlanningError(
                    "PHYSICAL_EVENT_TYPE_UNSUPPORTED",
                    "position requires a numeric indicator",
                )
            event_defs.append(
                PhysicalPosition(
                    alias,
                    value,
                    _parse_extreme_lookback(call.binding.slots.get("period", "")),
                )
            )
        event_refs[id(call)] = PhysicalEventRef(
            alias,
            STRING if call.name in _POSITION_CALLS else BOOLEAN,
        )
        for constraint in _call_constraints(call, catalog, root_id):
            if constraint.node_id not in seen_constraints:
                constraints.append(constraint)
                seen_constraints.add(constraint.node_id)

    for index, call in enumerate(scalar_calls):
        indicator_id = str(call.binding.slots.get("indicator_name", ""))
        field = _field_for_indicator(fields, indicator_id)
        expression = _lower_resolved_indicator(field)
        alias = f"projected_{index}"
        projections.append(PhysicalProjection(alias, expression))
        projected_refs[id(call)] = PhysicalProjectedRef(alias, expression.type)
        for constraint in _call_constraints(call, catalog, root_id):
            if constraint.node_id not in seen_constraints:
                constraints.append(constraint)
                seen_constraints.add(constraint.node_id)

    if default_latest and not date_scopes:
        stable_resource_id = catalog.resource(root_id).anchor_resource_id or root_id
        partition_key = catalog.resource(stable_resource_id).partition_key
        latest_constraint = PhysicalComparison(
            "=",
            PhysicalColumn(stable_resource_id, partition_key, TIME),
            PhysicalLatestValue(stable_resource_id, partition_key, TIME),
        )
        if latest_constraint.node_id not in seen_constraints:
            constraints.append(latest_constraint)

    predicate = _lower_crossing_predicate(
        event_predicate,
        {**event_refs, **projected_refs},
    )
    if event_absence:
        event_ref = next(iter(event_refs.values()))
        eligible_predicate = PhysicalBinary(
            "or",
            PhysicalComparison(
                "=", event_ref, PhysicalLiteral(True, BOOLEAN)
            ),
            PhysicalComparison(
                "=", event_ref, PhysicalLiteral(False, BOOLEAN)
            ),
            BOOLEAN,
        )
        plan: PhysicalPlan = PhysicalEventFilter(
            relation,
            tuple(event_defs),
            tuple(projections),
            predicate,
            tuple(constraints),
            "none",
            eligible_predicate,
            root_id,
        )
    else:
        plan = PhysicalEventFilter(
            relation,
            tuple(event_defs),
            tuple(projections),
            predicate,
            tuple(constraints),
        )
    if limit is not None:
        plan = PhysicalLimit(plan, limit[0], limit[1])
    validate_physical_plan(plan, catalog, expressions)
    selected_resource = "+".join(dict.fromkeys(joined))
    decision = PhysicalDecision(
        resource_id=selected_resource,
        feasible=True,
        cost=float(sum(catalog.resource(item).priority for item in dict.fromkeys(joined))),
        estimated=True,
        reason_code="PHYSICAL_EVENT_WINDOW_SELECTED",
        reason="set-based LAG event relation on stable security and trading-date keys",
        strategy_id=(
            "crossing_window_absence" if event_absence else "crossing_window"
        ),
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        selected_resource,
        (decision,),
        "crossing_window_absence" if event_absence else "crossing_window",
    )


def _plan_temporal_crossing_events(
    lowering: LoweringResult,
    calls: Tuple[CallExpr, ...],
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
) -> PhysicalPlanningResult:
    current = lowering.plan
    limit = None
    if isinstance(current, LogicalLimit):
        limit = (current.offset, current.count)
        current = current.input
    if not isinstance(current, (LogicalConsecutive, LogicalExist)):
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_TEMPORAL_PLAN_UNSUPPORTED",
            "temporal event plan requires one consecutive or existence relation",
        )
    event_filter = LogicalFilter(
        current.input,
        current.spec.predicate,
        current.schema,
    )
    event_result = _plan_crossing_events(
        replace(lowering, plan=event_filter),
        calls,
        catalog,
        fields,
        resource_ids,
        expressions,
        default_latest=False,
    )
    if not isinstance(event_result.plan, PhysicalEventFilter):
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_TEMPORAL_PLAN_UNSUPPORTED",
            "temporal event lowering requires a row-valued event projection",
        )
    event_plan = event_result.plan
    constrained_input = event_plan.input
    for constraint in event_plan.result_constraints:
        constrained_input = PhysicalFilter(constrained_input, constraint)
    plan: PhysicalPlan = PhysicalTemporal(
        PhysicalEventProjection(
            constrained_input,
            event_plan.events,
            event_plan.projections,
        ),
        event_plan.predicate,
        "CONS" if isinstance(current, LogicalConsecutive) else "EXIST",
        current.spec.comparator,
        current.spec.threshold,
        current.spec.maximum,
        current.spec.unit,
        current.spec.every,
        _lower_temporal_window(current.spec.window),
        current.spec.trading_sequence,
    )
    if limit is not None:
        plan = PhysicalLimit(plan, limit[0], limit[1])
    validate_physical_plan(plan, catalog, expressions)
    decision = replace(
        event_result.decisions[0],
        reason_code="PHYSICAL_EVENT_TEMPORAL_SELECTED",
        reason="event features are projected before typed temporal quantification",
        strategy_id="temporal_event_projection",
    )
    return PhysicalPlanningResult(
        plan,
        event_result.selected_resource,
        (decision,),
        "temporal_event_projection",
    )


def _lower_resolved_indicator(field: _ResolvedIndicator):
    return _physical_field_expression(field)


def _lower_crossing_predicate(expression, refs):
    if isinstance(expression, LiteralExpr):
        return _physical_literal(expression)
    if isinstance(expression, CallExpr) and id(expression) in refs:
        return refs[id(expression)]
    if isinstance(expression, BinaryExpr):
        return PhysicalBinary(
            expression.op,
            _lower_crossing_predicate(expression.left, refs),
            _lower_crossing_predicate(expression.right, refs),
            expression.type,
        )
    if isinstance(expression, ComparisonExpr):
        if expression.op == "~=":
            return _lower_approximate_comparison(
                _lower_crossing_predicate(expression.left, refs),
                _lower_crossing_predicate(expression.right, refs),
            )
        if expression.op == "between" and isinstance(expression.right, RangeExpr):
            value = _lower_crossing_predicate(expression.left, refs)
            lower = _lower_crossing_predicate(expression.right.lower, refs)
            upper = _lower_crossing_predicate(expression.right.upper, refs)
            return PhysicalBinary(
                "and",
                PhysicalComparison(">=" if expression.right.lower_inclusive else ">", value, lower),
                PhysicalComparison("<=" if expression.right.upper_inclusive else "<", value, upper),
                BOOLEAN,
            )
        return PhysicalComparison(
            expression.op,
            _lower_crossing_predicate(expression.left, refs),
            _lower_crossing_predicate(expression.right, refs),
        )
    if isinstance(expression, RangeExpr):
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_EXPRESSION_UNSUPPORTED",
            "standalone range values are only valid inside between comparisons",
        )
    raise PhysicalPlanningError(
        "PHYSICAL_EVENT_EXPRESSION_UNSUPPORTED",
        f"unsupported crossing expression {type(expression).__name__}",
    )


def _parse_extreme_lookback(value) -> Optional[int]:
    text = str(value or "").strip()
    if not text or text in {"历史", "史高", "史低"}:
        return None
    if _parse_fixed_event_period_start(text) is not None:
        return None
    if _parse_calendar_event_period(text) is not None:
        return None
    natural_period_sessions = {
        "半个月": 10,
        "上个月": 20,
        "上月": 20,
        "季度": 60,
        "一季度": 60,
        "一个季度": 60,
    }
    if text in natural_period_sessions:
        return natural_period_sessions[text]
    shorthand = re.fullmatch(
        r"(\d+|[零〇一二两三四五六七八九十百]+)内",
        text,
    )
    if shorthand:
        token = shorthand.group(1)
        return int(token) if token.isdigit() else _parse_small_chinese_integer(token)
    match = re.fullmatch(
        r"(?:近|最近|过去)?(\d+|[零〇一二两三四五六七八九十百]+)(?:个)?(交易日|日|天|周|星期|月|个月|季度|季|年)(?:内)?",
        text,
    )
    if not match:
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_PERIOD_UNSUPPORTED",
            f"record extreme period requires an explicit trading-session count: {text}",
        )
    token = match.group(1)
    amount = int(token) if token.isdigit() else _parse_small_chinese_integer(token)
    sessions_per_unit = {
        "交易日": 1,
        "日": 1,
        "天": 1,
        "周": 5,
        "星期": 5,
        "月": 20,
        "个月": 20,
        "季度": 60,
        "季": 60,
        "年": 250,
    }
    return amount * sessions_per_unit[match.group(2)]


def _parse_fixed_event_period_start(value) -> Optional[str]:
    text = str(value or "").strip()
    match = re.fullmatch(r"(.+?)(?:以|之)来", text)
    if not match:
        return None
    boundary = parse_date_constraint(match.group(1))
    if boundary.kind != "exact" or not boundary.start:
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_PERIOD_UNSUPPORTED",
            f"event period start must be one exact calendar date: {text}",
        )
    return boundary.start


def _parse_calendar_event_period(value) -> Optional[Tuple[int, int]]:
    text = str(value or "").strip()
    halves = {
        "上半年": (1, 6),
        "今年上半年": (1, 6),
        "下半年": (7, 12),
        "今年下半年": (7, 12),
    }
    if text in halves:
        return halves[text]
    match = re.fullmatch(
        r"今年(?P<start>\d+|[一二三四五六七八九十]+)月(?:到|至|-)(?P<end>\d+|[一二三四五六七八九十]+)月",
        text,
    )
    if not match:
        return None
    values = []
    for key in ("start", "end"):
        token = match.group(key)
        values.append(
            int(token) if token.isdigit() else _parse_small_chinese_integer(token)
        )
    start, end = values
    if not 1 <= start <= end <= 12:
        raise PhysicalPlanningError(
            "PHYSICAL_EVENT_PERIOD_UNSUPPORTED",
            f"record extreme month range is invalid: {text}",
        )
    return start, end


def _parse_small_chinese_integer(text: str) -> int:
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text == "十":
        return 10
    if "百" in text:
        head, tail = text.split("百", 1)
        value = digits.get(head, 1) * 100
        return value + (_parse_small_chinese_integer(tail) if tail else 0)
    if "十" in text:
        head, tail = text.split("十", 1)
        return digits.get(head, 1) * 10 + (digits.get(tail, 0) if tail else 0)
    if text in digits and digits[text] > 0:
        return digits[text]
    raise PhysicalPlanningError(
        "PHYSICAL_EVENT_PERIOD_UNSUPPORTED",
        f"record extreme period has an unsupported count: {text}",
    )


def _build_join_relation(
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    catalog: PhysicalCatalog,
):
    resources = tuple(catalog.resource(resource_id) for resource_id in resource_ids)
    entities = {resource.logical_entity for resource in resources}
    if len(entities) != 1:
        raise PhysicalPlanningError(
            "PHYSICAL_MULTI_RESOURCE_ENTITY_MISMATCH",
            "multi-resource plan crosses logical entities",
        )
    anchor_ids = {
        resource.anchor_resource_id
        for resource in resources
        if resource.anchor_resource_id is not None
    }
    if "official_basic" in resource_ids:
        root_id = "official_basic"
    elif len(anchor_ids) == 1:
        root_id = next(iter(anchor_ids))
    else:
        raise PhysicalPlanningError(
            "PHYSICAL_STABLE_ANCHOR_UNAVAILABLE",
            "multi-resource plan has no unique stable anchor",
        )
    root = catalog.resource(root_id)
    relation: PhysicalPlan = PhysicalTableScan(
        root_id,
        _scan_columns(fields, resource_id=root_id),
    )
    joined_ids = tuple(sorted(set(resource_ids) - {root_id}))
    for resource_id in joined_ids:
        resource = catalog.resource(resource_id)
        key_names = tuple(
            key for key in root.stable_keys if key in resource.stable_keys
        )
        if not {"mktcode", "tgtcode"}.issubset(key_names):
            raise PhysicalPlanningError(
                "PHYSICAL_STABLE_KEY_UNAVAILABLE",
                f"resources {root_id} and {resource_id} lack stable security join keys",
            )
        right = PhysicalTableScan(
            resource_id,
            _scan_columns(fields, resource_id=resource_id),
        )
        keys = tuple(
            (
                PhysicalColumn(root_id, key, TIME if key == "bizdate" else (STRING if key == "tgtcode" else NUMERIC)),
                PhysicalColumn(resource_id, key, TIME if key == "bizdate" else (STRING if key == "tgtcode" else NUMERIC)),
            )
            for key in key_names
        )
        relation = PhysicalJoin(relation, right, "left", keys)
    return relation, root_id, (root_id, *joined_ids)


def _contains_temporal_plan(plan) -> bool:
    current = plan
    while isinstance(current, (LogicalFilter, LogicalLimit, LogicalRank, LogicalStage, LogicalConsecutive, LogicalExist)):
        if isinstance(current, (LogicalConsecutive, LogicalExist)):
            return True
        current = current.operation if isinstance(current, LogicalStage) else current.input
    return False


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


def _prefix_candidate_decision(
    strategy,
    catalog,
    statistics,
    allow_shadow_strategies,
    *,
    default_eligible=True,
):
    scan = catalog.resource(strategy.scan_resource_id)
    prefix = catalog.resource(strategy.prefix_resource_id)
    selection_eligible = (
        strategy.selection_mode == "active" and default_eligible
    ) or allow_shadow_strategies
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
                        if selection_eligible
                        else "PHYSICAL_PREFIX_SHADOW_CANDIDATE"
                    ),
                    reason=(
                        "cost is scan bytes plus two conservative prefix resource accesses; "
                        f"selection mode is {strategy.selection_mode}; "
                        f"plan-shape calibration is {'eligible' if default_eligible else 'shadow'}"
                    ),
                    cost_unit="bytes",
                    cost_components=components,
                    selection_eligible=selection_eligible,
                )
    return PhysicalDecision(
        resource_id=prefix.resource_id,
        feasible=True,
        cost=float(scan.priority + prefix.priority * 2),
        estimated=True,
        reason_code="PHYSICAL_PREFIX_STATISTICS_INCOMPLETE",
        reason="catalog priority fallback for prefix candidate",
        selection_eligible=selection_eligible,
    )


def _aggregate_strategy_decision(
    strategy,
    catalog,
    statistics,
    allow_shadow_strategies,
    *,
    semantic_eligible,
):
    if isinstance(strategy, PhysicalPrefixAggregateStrategy):
        resource_id = strategy.prefix_resource_id
        access_fraction = strategy.access_fraction_hint
        access_multiplier = 1.0 if semantic_eligible else 2.0
        reason_label = (
            "one partition-pruned full-history prefix endpoint lookup"
            if semantic_eligible
            else "two bounded-window prefix endpoint lookups"
        )
    else:
        resource_id = strategy.materialized_resource_id
        access_fraction = strategy.partition_fraction_hint
        access_multiplier = 1.0
        reason_label = "partition-pruned materialized feature lookup"
    selection_eligible = (
        strategy.selection_mode == "active" and semantic_eligible
    ) or allow_shadow_strategies
    resource = catalog.resource(resource_id)
    measured_bytes = None
    estimated = True
    if statistics is not None:
        try:
            item = statistics.resource(resource_id)
        except KeyError:
            item = None
        if item is not None and item.row_count_available and item.data_size_bytes > 0:
            measured_bytes = float(item.data_size_bytes)
            estimated = False
    if measured_bytes is None and statistics is not None:
        try:
            source = statistics.resource(strategy.scan_resource_id)
        except KeyError:
            source = None
        if source is not None and source.row_count_available and source.data_size_bytes > 0:
            measured_bytes = float(source.data_size_bytes)
    if measured_bytes is not None:
        effective_bytes = measured_bytes * access_fraction * access_multiplier
        return PhysicalDecision(
            resource_id=resource_id,
            feasible=True,
            cost=effective_bytes,
            estimated=estimated,
            reason_code=(
                "PHYSICAL_AGGREGATE_ACCELERATION_SELECTED"
                if selection_eligible
                else "PHYSICAL_AGGREGATE_ACCELERATION_SHADOW"
            ),
            reason=(
                f"cost models {reason_label}; access fraction {access_fraction:.6f}; "
                f"selection mode is {strategy.selection_mode}; "
                f"semantic equivalence is {'proven' if semantic_eligible else 'shadow-only'}"
            ),
            cost_unit="effective_bytes",
            cost_components=(
                ("catalog_bytes", measured_bytes),
                ("access_fraction", access_fraction),
                ("access_multiplier", access_multiplier),
            ),
            selection_eligible=selection_eligible,
        )
    return PhysicalDecision(
        resource_id=resource_id,
        feasible=True,
        cost=float(resource.priority),
        estimated=True,
        reason_code="PHYSICAL_AGGREGATE_ACCELERATION_STATISTICS_INCOMPLETE",
        reason=f"catalog priority fallback for {reason_label}",
        selection_eligible=selection_eligible,
    )


def _prefix_aggregate_semantically_eligible(strategy, window, statistics) -> bool:
    if statistics is None:
        return False
    try:
        source = statistics.resource(strategy.scan_resource_id)
    except KeyError:
        return False
    return bool(
        source.partition_value_count is not None
        and window >= source.partition_value_count
    )


def _prefix_aggregate_as_of_date(strategy, statistics) -> Optional[str]:
    if statistics is None:
        return None
    try:
        source = statistics.resource(strategy.scan_resource_id)
    except KeyError:
        return None
    return source.partition_max


def _collect_fields(
    plan,
    catalog: PhysicalCatalog,
    expressions: Optional[PhysicalExpressionRegistry],
) -> Tuple[_ResolvedIndicator, ...]:
    logical_expressions = tuple(_logical_expressions(plan))
    unsupported_roots = tuple(
        root
        for root in _logical_roots(plan)
        if not isinstance(root, LogicalDomainScan)
    )
    if unsupported_roots:
        raise PhysicalPlanningError(
            "PHYSICAL_LOGICAL_PLAN_UNSUPPORTED",
            f"unsupported logical root {type(unsupported_roots[0]).__name__}",
        )

    fields = []
    security_scope_required = False
    scope_catalog = current_security_scope_catalog()
    external_scope_catalog = current_external_scope_catalog()
    for expression in logical_expressions:
        for call in _walk_calls(expression):
            if _configured_function_signature(call) is not None:
                continue
            if (
                call.name
                not in _DIRECT_FIELD_CALLS | _WINDOW_EVENT_CALLS | {"belong_industry"}
                or call.binding is None
            ):
                raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {call.name}")
            if call.scope_expression is not None:
                resolved_scopes = _resolve_scope_atoms(
                    call.scope_expression,
                    scope_catalog,
                    external_scope_catalog,
                )
                security_scope_required = security_scope_required or any(
                    kind == "security" for kind, _ in resolved_scopes
                )
            _reject_unmaterialized_constraints(call)
            indicator_ids = (
                (
                    call.binding.slots.get("indicator_name_1", ""),
                    call.binding.slots.get("indicator_name_2", ""),
                )
                if call.name in _CROSSING_CALLS | _PATTERN_CALLS
                else (call.binding.slots.get("indicator_name", ""),)
            )
            for indicator_id in indicator_ids:
                if _is_universe_call(call):
                    continue
                if indicator_id == "是否T+0":
                    fields.append(
                        _ResolvedIndicator(
                            "是否T+0",
                            "official_basic",
                            "boolean",
                        )
                    )
                    continue
                if indicator_id == "稳定证券顺序":
                    fields.append(
                        _ResolvedIndicator(
                            "稳定证券顺序",
                            "official_basic",
                            "numeric",
                        )
                    )
                    continue
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
    if security_scope_required:
        fields.append(
            _ResolvedIndicator(
                "__security_scope_name",
                "official_security",
                "string",
                direct_column="name",
            )
        )
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


def _logical_expressions(plan):
    if isinstance(plan, LogicalSetOperation):
        yield from _logical_expressions(plan.left)
        yield from _logical_expressions(plan.right)
        return
    if isinstance(plan, LogicalStage):
        yield from _logical_expressions(plan.operation)
        return
    if isinstance(plan, LogicalFilter):
        yield plan.predicate
    elif isinstance(plan, (LogicalConsecutive, LogicalExist)):
        yield plan.spec.predicate
    elif isinstance(plan, LogicalRank):
        yield plan.order_by
    if isinstance(
        plan,
        (LogicalFilter, LogicalLimit, LogicalRank, LogicalConsecutive, LogicalExist),
    ):
        yield from _logical_expressions(plan.input)


def _logical_roots(plan):
    if isinstance(plan, LogicalSetOperation):
        yield from _logical_roots(plan.left)
        yield from _logical_roots(plan.right)
    elif isinstance(plan, LogicalStage):
        yield from _logical_roots(plan.operation)
    elif isinstance(
        plan,
        (LogicalFilter, LogicalLimit, LogicalRank, LogicalConsecutive, LogicalExist),
    ):
        yield from _logical_roots(plan.input)
    else:
        yield plan


def _is_universe_call(expression) -> bool:
    return (
        isinstance(expression, CallExpr)
        and expression.name == "indicator"
        and expression.binding is not None
        and not str(expression.binding.slots.get("indicator_name", "")).strip()
    )


def _contains_universe_selector(plan) -> bool:
    return any(
        _is_universe_call(call)
        for expression in _logical_expressions(plan)
        for call in _walk_calls(expression)
    )


def _validate_universe_contract(plan) -> None:
    for expression in _logical_expressions(plan):
        _validate_universe_expression(expression)


def _validate_universe_expression(expression) -> None:
    if isinstance(expression, ComparisonExpr):
        if _is_universe_call(expression.left):
            if not (
                expression.op == "="
                and isinstance(expression.right, LiteralExpr)
                and expression.right.type is STRING
                and expression.right.value == "all"
            ):
                raise PhysicalPlanningError(
                    "PHYSICAL_UNIVERSE_COMPARISON_UNSUPPORTED",
                    "security universe selection requires indicator(...) = 'all'",
                )
            return
        if _contains_universe_call(expression.left) or _contains_universe_call(expression.right):
            raise PhysicalPlanningError(
                "PHYSICAL_UNIVERSE_COMPARISON_UNSUPPORTED",
                "security universe selector must be the direct left operand of = 'all'",
            )
        _validate_universe_expression(expression.left)
        _validate_universe_expression(expression.right)
        return
    if isinstance(expression, BinaryExpr):
        _validate_universe_expression(expression.left)
        _validate_universe_expression(expression.right)
        return
    if isinstance(expression, RangeExpr):
        _validate_universe_expression(expression.lower)
        _validate_universe_expression(expression.upper)
        return
    if _is_universe_call(expression):
        raise PhysicalPlanningError(
            "PHYSICAL_UNIVERSE_COMPARISON_UNSUPPORTED",
            "security universe selector requires an explicit = 'all' comparison",
        )


def _contains_universe_call(expression) -> bool:
    return any(_is_universe_call(call) for call in _walk_calls(expression))


def _reject_unmaterialized_constraints(call: CallExpr) -> None:
    materialized = {"indicator_name", "market", "date", "direction", "agg_func"}
    if call.name in _CROSSING_CALLS | _PATTERN_CALLS:
        materialized.update({"indicator_name_1", "indicator_name_2"})
    if call.name in _EXTREME_CALLS | _POSITION_CALLS:
        materialized.add("period")
    if call.scope_expression is not None:
        materialized.update({"filter_scope", "keywords"})
    ignored = {
        slot: value
        for slot, value in call.binding.slots.items()
        if slot not in materialized and str(value).strip()
    }
    if ignored:
        names = ", ".join(sorted(ignored))
        raise PhysicalPlanningError(
            "PHYSICAL_CONSTRAINT_UNSUPPORTED",
            f"physical planner cannot yet materialize non-empty slot(s): {names}",
        )


def _build_stage_rank(
    input_plan: PhysicalPlan,
    logical_rank: LogicalRank,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
) -> PhysicalStageRank:
    if not isinstance(logical_rank.order_by, CallExpr) or logical_rank.order_by.binding is None:
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
            "stage rank requires one bound rank call",
        )
    indicator_id = logical_rank.order_by.binding.slots.get("indicator_name", "")
    field = _field_for_indicator(fields, indicator_id)
    measure_resource = catalog.resource(field.resource_id)
    measure_input: PhysicalPlan = PhysicalScan(
        field.resource_id,
        _scan_columns((field,)),
        None,
        measure_resource.anchor_resource_id,
    )
    constraints = list(
        _call_constraints(logical_rank.order_by, catalog, field.resource_id)
    )
    function = str(
        logical_rank.order_by.binding.slots.get("agg_func", "")
    ).strip().upper() or None
    if function is not None and function not in _SET_AGGREGATE_FUNCTIONS:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
            f"stage rank aggregate requires a dedicated contract: {function}",
        )
    date = str(logical_rank.order_by.binding.slots.get("date", "")).strip()
    collapse_latest = False
    if not date and function is None:
        stable_id = measure_resource.anchor_resource_id or field.resource_id
        partition_key = catalog.resource(stable_id).partition_key
        constraints.append(
            PhysicalComparison(
                "=",
                PhysicalColumn(stable_id, partition_key, TIME),
                PhysicalLatestValue(stable_id, partition_key, TIME),
            )
        )
    elif date and function is None:
        typed_date = logical_rank.order_by.date_constraint or parse_date_constraint(date)
        collapse_latest = typed_date.kind not in {
            "relative",
            "exact",
            "relative_session",
        }
    for constraint in constraints:
        measure_input = PhysicalFilter(measure_input, constraint)
    bound, percentage, upper_bound = _physical_rank_bounds(
        logical_rank.bound,
        logical_rank.comparator,
        logical_rank.upper_bound,
    )
    return PhysicalStageRank(
        input_plan,
        measure_input,
        _physical_field_expression(field),
        function.lower() if function else None,
        logical_rank.direction,
        bound,
        logical_rank.comparator,
        percentage,
        input_plan.stage_index + 1
        if isinstance(input_plan, PhysicalStageRank)
        else 1,
        collapse_latest,
        upper_bound,
        logical_rank.lower_inclusive,
        logical_rank.upper_inclusive,
    )


def _lower_plan(
    plan,
    catalog: PhysicalCatalog,
    resource_id: str,
    fields: Tuple[_ResolvedIndicator, ...],
    expression_overrides=None,
    base_plan: Optional[PhysicalPlan] = None,
    allowed_resource_ids=None,
) -> PhysicalPlan:
    if isinstance(plan, LogicalDomainScan):
        if base_plan is not None:
            return base_plan
        columns = _scan_columns(fields)
        resource = catalog.resource(resource_id)
        return PhysicalScan(resource_id, columns, None, resource.anchor_resource_id)
    if isinstance(plan, LogicalFilter):
        predicate = _lower_expr(
            plan.predicate,
            catalog,
            resource_id,
            fields,
            expression_overrides=expression_overrides,
            allowed_resource_ids=allowed_resource_ids,
        )
        return PhysicalFilter(
            _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides, base_plan, allowed_resource_ids),
            _deduplicate_and(predicate),
        )
    if isinstance(plan, LogicalLimit):
        return PhysicalLimit(
            _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides, base_plan, allowed_resource_ids),
            plan.offset,
            plan.count,
        )
    if isinstance(plan, LogicalRank):
        input_plan = _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides, base_plan, allowed_resource_ids)
        if not isinstance(input_plan, (PhysicalScan, PhysicalFilter, PhysicalJoin, PhysicalTableScan)):
            return _build_stage_rank(input_plan, plan, catalog, fields)
        rank_constraints = list(
            _call_constraints(plan.order_by, catalog, resource_id)
        )
        if isinstance(plan.order_by, CallExpr) and plan.order_by.binding is not None:
            date = str(plan.order_by.binding.slots.get("date", "")).strip()
            if not date:
                resource = catalog.resource(resource_id)
                stable_id = resource.anchor_resource_id or resource_id
                partition_key = catalog.resource(stable_id).partition_key
                rank_constraints.append(
                    PhysicalComparison(
                        "=",
                        PhysicalColumn(stable_id, partition_key, TIME),
                        PhysicalLatestValue(stable_id, partition_key, TIME),
                    )
                )
        for constraint in rank_constraints:
            input_plan = PhysicalFilter(input_plan, constraint)
        expression = _lower_expr(plan.order_by, catalog, resource_id, fields, allow_rank=True, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids)
        bound, percentage, upper_bound = _physical_rank_bounds(
            plan.bound,
            plan.comparator,
            plan.upper_bound,
        )
        return PhysicalRank(
            input_plan,
            expression,
            plan.direction,
            bound,
            plan.comparator,
            percentage,
            upper_bound,
            plan.lower_inclusive,
            plan.upper_inclusive,
        )
    if isinstance(plan, (LogicalConsecutive, LogicalExist)):
        return PhysicalTemporal(
            _lower_plan(plan.input, catalog, resource_id, fields, expression_overrides, base_plan, allowed_resource_ids),
            _lower_expr(plan.spec.predicate, catalog, resource_id, fields, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
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
        return _lower_plan(plan.operation, catalog, resource_id, fields, expression_overrides, base_plan, allowed_resource_ids)
    raise PhysicalPlanningError("PHYSICAL_LOGICAL_PLAN_UNSUPPORTED", f"unsupported logical node {type(plan).__name__}")


def _deduplicate_and(predicate):
    conjuncts = []

    def collect(expression):
        if isinstance(expression, PhysicalBinary) and expression.op.lower() == "and":
            collect(expression.left)
            collect(expression.right)
        else:
            conjuncts.append(expression)

    collect(predicate)
    unique = []
    seen = set()
    for expression in conjuncts:
        expression = _normalize_external_exists_boolean(expression)
        if expression.node_id in seen:
            continue
        seen.add(expression.node_id)
        unique.append(expression)
    result = unique[0]
    for expression in unique[1:]:
        result = PhysicalBinary("and", result, expression, BOOLEAN)
    return result


def _normalize_external_exists_boolean(expression):
    if not isinstance(expression, PhysicalComparison) or expression.op not in {"=", "!="}:
        return expression
    for candidate, literal in (
        (expression.left, expression.right),
        (expression.right, expression.left),
    ):
        if not (
            isinstance(candidate, PhysicalExternalExists)
            and isinstance(literal, PhysicalLiteral)
            and isinstance(literal.value, bool)
        ):
            continue
        expected = literal.value if expression.op == "=" else not literal.value
        if expected:
            return candidate
    return expression


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
    if window.kind == "relative_session" and window.amount:
        return PhysicalTemporalWindow(
            "session_slice",
            lookback_sessions=1,
            session_offset=window.amount,
        )
    if window.kind == "session_slice" and window.amount:
        return PhysicalTemporalWindow(
            "session_slice",
            lookback_sessions=window.amount,
            session_offset=window.offset,
        )
    if window.kind == "before_period_sessions" and window.amount and window.unit:
        return PhysicalTemporalWindow(
            "boundary_sessions",
            lookback_sessions=window.amount,
            calendar_unit=window.unit,
            calendar_offset=window.offset,
            boundary_direction="before",
            boundary_kind="period",
        )
    if window.kind == "after_date_sessions" and window.amount and window.start:
        return PhysicalTemporalWindow(
            "boundary_sessions",
            lookback_sessions=window.amount,
            boundary_direction="after",
            boundary_kind="date",
            boundary_date=window.start,
        )
    if window.kind in {"before_anchor_sessions", "after_anchor_sessions"} and window.amount:
        return PhysicalTemporalWindow(
            "boundary_sessions",
            lookback_sessions=window.amount,
            calendar_offset=window.offset,
            anchor_month=window.month,
            anchor_day=window.day,
            boundary_direction=(
                "before" if window.kind == "before_anchor_sessions" else "after"
            ),
            boundary_kind="anchor",
        )
    if window.kind == "recent_calendar" and window.amount and window.unit:
        return PhysicalTemporalWindow(
            "recent_calendar",
            calendar_amount=window.amount,
            calendar_unit=window.unit,
        )
    if window.kind == "dynamic_period" and window.unit:
        return PhysicalTemporalWindow(
            "dynamic_period",
            calendar_amount=1,
            calendar_unit=window.unit,
            calendar_offset=window.offset,
        )
    if window.kind == "anchor_calendar" and window.unit:
        return PhysicalTemporalWindow(
            "anchor_calendar",
            calendar_amount=1,
            calendar_unit=window.unit,
            anchor_month=window.month,
            anchor_day=window.day,
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
    allowed_resource_ids=None,
):
    if isinstance(expression, LiteralExpr):
        return _physical_literal(expression)
    if isinstance(expression, CallExpr):
        if _configured_function_signature(expression) is not None:
            return _lower_configured_function(
                expression,
                lambda item: _lower_expr(
                    item,
                    catalog,
                    resource_id,
                    fields,
                    allow_rank=allow_rank,
                    expression_overrides=expression_overrides,
                    allowed_resource_ids=allowed_resource_ids,
                ),
            )
        if expression.name not in _DIRECT_FIELD_CALLS or expression.binding is None:
            raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported physical call {expression.name}")
        if expression.name == "rank" and not allow_rank:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED",
                "rank inside a scalar expression requires an explicit window plan",
            )
        if _is_universe_call(expression):
            return PhysicalLiteral("all", STRING)
        indicator_id = expression.binding.slots.get("indicator_name", "")
        if expression_overrides and indicator_id.casefold() in expression_overrides:
            return expression_overrides[indicator_id.casefold()]
        try:
            field = _field_for_indicator(fields, indicator_id)
        except KeyError as exc:
            raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", f"no controlled physical mapping for indicator {indicator_id}") from exc
        allowed = allowed_resource_ids or frozenset({resource_id})
        if field.resource_id not in allowed:
            raise PhysicalPlanningError("PHYSICAL_MULTI_RESOURCE_UNSUPPORTED", "expression spans multiple physical resources")
        return _physical_field_expression(field)
    if isinstance(expression, BinaryExpr):
        return PhysicalBinary(
            expression.op,
            _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
            _lower_expr(expression.right, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
            expression.type,
        )
    if isinstance(expression, ComparisonExpr):
        if expression.op == "~=":
            result = _lower_approximate_comparison(
                _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
                _lower_expr(expression.right, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
            )
            return _apply_call_constraints(result, expression, catalog, resource_id)
        if isinstance(expression.right, RangeExpr) and expression.op == "between":
            value = _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids)
            lower = _lower_expr(expression.right.lower, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids)
            upper = _lower_expr(expression.right.upper, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids)
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
                _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
                _lower_expr(expression.right, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
            )
        return _apply_call_constraints(result, expression, catalog, resource_id)
    raise PhysicalPlanningError("PHYSICAL_EXPRESSION_UNSUPPORTED", f"unsupported expression {type(expression).__name__}")


def _type_from_name(value_type: str) -> OfficialType:
    try:
        return _TYPE_MAP[value_type]
    except KeyError as exc:
        raise PhysicalPlanningError("PHYSICAL_TYPE_UNSUPPORTED", f"unsupported physical type {value_type}") from exc


def _physical_literal(expression: LiteralExpr) -> PhysicalLiteral:
    value = expression.value
    if (
        expression.type is NUMERIC
        and isinstance(value, str)
        and re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)%", value)
    ):
        numeric = float(value[:-1])
        value = int(numeric) if numeric.is_integer() else numeric
    return PhysicalLiteral(value, expression.type)


def _lower_approximate_comparison(left, right):
    if left.type is not NUMERIC or right.type is not NUMERIC:
        raise PhysicalPlanningError(
            "PHYSICAL_APPROXIMATION_TYPE_UNSUPPORTED",
            "physical approximate equality currently requires numeric operands",
        )
    policy = current_numeric_approximation_policy()
    difference = PhysicalAbs(
        PhysicalBinary("-", left, right, NUMERIC),
        NUMERIC,
    )
    magnitude = PhysicalGreatest(
        (PhysicalAbs(left, NUMERIC), PhysicalAbs(right, NUMERIC)),
        NUMERIC,
    )
    relative_bound = PhysicalBinary(
        "*",
        PhysicalLiteral(policy.relative_tolerance, NUMERIC),
        magnitude,
        NUMERIC,
    )
    tolerance = PhysicalGreatest(
        (PhysicalLiteral(policy.absolute_tolerance, NUMERIC), relative_bound),
        NUMERIC,
    )
    return PhysicalComparison("<=", difference, tolerance)


def _rank_bound(expression, comparator: str) -> Tuple[PhysicalLiteral, bool]:
    if not isinstance(expression, LiteralExpr):
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_BOUND_UNSUPPORTED",
            "physical rank requires a numeric or percentage literal bound",
        )
    percentage = isinstance(expression.value, str) and expression.value.endswith("%")
    bound = _physical_literal(expression)
    if (
        not isinstance(bound.value, (int, float))
        or isinstance(bound.value, bool)
        or bound.value < 0
        or (bound.value == 0 and comparator not in {">", ">="})
        or (percentage and bound.value > 100)
    ):
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_BOUND_UNSUPPORTED",
            "rank bound must be positive and percentage bounds cannot exceed 100%",
        )
    return bound, percentage


def _physical_rank_bounds(expression, comparator: str, upper_expression=None):
    lower, percentage = _rank_bound(
        expression,
        ">=" if comparator == "between" else comparator,
    )
    if comparator != "between":
        if upper_expression is not None:
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_BOUND_UNSUPPORTED",
                "scalar rank comparison cannot carry an upper bound",
            )
        return lower, percentage, None
    if upper_expression is None:
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_BOUND_UNSUPPORTED",
            "rank range requires an upper bound",
        )
    upper, upper_percentage = _rank_bound(upper_expression, "<=")
    if upper_percentage != percentage or upper.value < lower.value:
        raise PhysicalPlanningError(
            "PHYSICAL_RANK_BOUND_UNSUPPORTED",
            "rank range bounds must use one unit and increase from lower to upper",
        )
    return lower, percentage, upper


def _resolve_indicator(
    indicator_id: str,
    catalog: PhysicalCatalog,
    expressions: Optional[PhysicalExpressionRegistry],
) -> _ResolvedIndicator:
    try:
        field = catalog.indicator(indicator_id)
    except KeyError:
        dynamic = _dynamic_moving_average(indicator_id)
        if dynamic is not None:
            return dynamic
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


def _dynamic_moving_average(indicator_id: str):
    match = re.fullmatch(r"(\d{1,4})日均(量)?线", str(indicator_id).strip())
    if not match:
        return None
    window = int(match.group(1))
    if not 1 <= window <= 1000:
        return None
    is_volume = bool(match.group(2))
    return _ResolvedIndicator(
        str(indicator_id).strip(),
        "official_basic",
        "numeric",
        prefix_average=PhysicalPrefixAverage(
            "official_basic_prefix",
            "volume_prefix" if is_volume else "close_prefix",
            "volume_count_prefix" if is_volume else "close_count_prefix",
            window,
            1.0 if is_volume else 10000.0,
            NUMERIC,
        ),
    )


def _dynamic_prefix_alias(field: _ResolvedIndicator) -> str:
    assert field.prefix_average is not None
    kind = "volume" if "volume" in field.prefix_average.sum_column else "price"
    return f"dynamic_{kind}_average_{field.prefix_average.window}"


def _dynamic_prefix_projections(fields: Tuple[_ResolvedIndicator, ...]):
    projections = {}
    for field in fields:
        if field.prefix_average is None:
            continue
        alias = _dynamic_prefix_alias(field)
        projections[alias] = PhysicalProjection(alias, field.prefix_average)
    return tuple(projections[key] for key in sorted(projections))


def _with_dynamic_prefixes(plan: PhysicalPlan, fields):
    projections = _dynamic_prefix_projections(tuple(fields))
    if not projections:
        return plan
    if isinstance(plan, (PhysicalFilter, PhysicalLimit, PhysicalRank)):
        return replace(plan, input=_with_dynamic_prefixes(plan.input, fields))
    if isinstance(plan, PhysicalPrefixJoin):
        combined = {item.alias: item for item in (*plan.projections, *projections)}
        return replace(
            plan,
            projections=tuple(combined[key] for key in sorted(combined)),
        )
    if isinstance(plan, (PhysicalScan, PhysicalTableScan, PhysicalJoin)):
        return PhysicalPrefixJoin(plan, projections, None)
    raise PhysicalPlanningError(
        "PHYSICAL_DYNAMIC_PREFIX_PLAN_UNSUPPORTED",
        f"dynamic moving average cannot attach to {type(plan).__name__}",
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


def _scan_columns(fields: Tuple[_ResolvedIndicator, ...], resource_id: Optional[str] = None) -> Tuple[PhysicalColumn, ...]:
    columns = {}
    for field in fields:
        if resource_id is not None and field.resource_id != resource_id:
            continue
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


def _configured_function_signature(expression: CallExpr):
    catalog = current_function_catalog()
    signature = catalog.resolve(expression.name) if catalog is not None else None
    if signature is None or signature.argument_mode != "expressions":
        return None
    return signature


def _lower_configured_function(expression: CallExpr, lower_argument):
    signature = _configured_function_signature(expression)
    if signature is None:
        raise PhysicalPlanningError(
            "PHYSICAL_FUNCTION_TEMPLATE_UNAVAILABLE",
            f"configured function is unavailable: {expression.name}",
        )
    arguments = tuple(lower_argument(item) for item in expression.args)
    operation = signature.lowering_op
    if operation == "abs" and len(arguments) == 1:
        return PhysicalAbs(arguments[0], expression.type)
    if operation == "greatest" and len(arguments) == 2:
        return PhysicalGreatest(arguments, expression.type)
    binary = {
        "add": "+",
        "subtract": "-",
        "multiply": "*",
    }
    if operation in binary and len(arguments) == 2:
        return PhysicalBinary(binary[operation], arguments[0], arguments[1], expression.type)
    if operation == "safe_divide" and len(arguments) == 2:
        return PhysicalBinary(
            "/",
            arguments[0],
            PhysicalNullIf(
                arguments[1],
                PhysicalLiteral(0, arguments[1].type),
                arguments[1].type,
            ),
            expression.type,
        )
    comparison = {"greater_than": ">", "less_than": "<"}
    if operation in comparison and len(arguments) == 2:
        return PhysicalComparison(comparison[operation], arguments[0], arguments[1])
    raise PhysicalPlanningError(
        "PHYSICAL_FUNCTION_TEMPLATE_UNSUPPORTED",
        f"unsupported configured function template {signature.template_kind}/{operation}",
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
        market_expression = call.market_expression or parse_market_expression(market)
        constraints.append(_lower_market_expression(market_expression, stable_resource_id))
    if call.scope_expression is not None:
        constraints.append(
            _lower_scope_expression(
                call.scope_expression,
                current_security_scope_catalog(),
                current_external_scope_catalog(),
                stable_resource_id,
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
        typed_date = call.date_constraint or parse_date_constraint(date)
        if typed_date.kind == "relative" and typed_date.anchor == "today":
            constraints.append(
                PhysicalComparison(
                    "=",
                    column,
                    PhysicalLatestValue(stable_resource_id, partition_key, TIME),
                )
            )
        elif typed_date.kind == "exact" and typed_date.start:
            constraints.append(
                PhysicalComparison("=", column, PhysicalLiteral(typed_date.start, TIME))
            )
        elif typed_date.kind == "relative_session" and typed_date.amount:
            constraints.append(
                PhysicalComparison(
                    "=",
                    column,
                    PhysicalNthLatestValue(
                        stable_resource_id,
                        partition_key,
                        typed_date.amount,
                        TIME,
                    ),
                )
            )
        elif typed_date.kind == "recent_sessions" and typed_date.amount:
            constraints.append(
                PhysicalRecentSessions(
                    stable_resource_id,
                    partition_key,
                    typed_date.amount,
                )
            )
        elif typed_date.kind == "session_slice" and typed_date.amount:
            constraints.append(
                PhysicalRecentSessions(
                    stable_resource_id,
                    partition_key,
                    typed_date.amount,
                    offset=typed_date.offset,
                )
            )
        elif typed_date.kind == "before_period_sessions" and typed_date.amount and typed_date.unit:
            constraints.append(
                PhysicalSessionBoundaryRange(
                    stable_resource_id,
                    partition_key,
                    "before",
                    "period",
                    typed_date.amount,
                    unit=typed_date.unit,
                    offset=typed_date.offset,
                )
            )
        elif typed_date.kind == "after_date_sessions" and typed_date.amount and typed_date.start:
            constraints.append(
                PhysicalSessionBoundaryRange(
                    stable_resource_id,
                    partition_key,
                    "after",
                    "date",
                    typed_date.amount,
                    boundary_date=typed_date.start,
                )
            )
        elif typed_date.kind in {"before_anchor_sessions", "after_anchor_sessions"} and typed_date.amount:
            constraints.append(
                PhysicalSessionBoundaryRange(
                    stable_resource_id,
                    partition_key,
                    "before" if typed_date.kind == "before_anchor_sessions" else "after",
                    "anchor",
                    typed_date.amount,
                    offset=typed_date.offset,
                    month=typed_date.month,
                    day=typed_date.day,
                )
            )
        elif typed_date.kind == "dynamic_period" and typed_date.unit:
            constraints.append(
                PhysicalDynamicDateRange(
                    stable_resource_id,
                    partition_key,
                    "period",
                    typed_date.unit,
                    offset=typed_date.offset,
                )
            )
        elif typed_date.kind == "recent_calendar" and typed_date.amount and typed_date.unit:
            constraints.append(
                PhysicalDynamicDateRange(
                    stable_resource_id,
                    partition_key,
                    "recent",
                    typed_date.unit,
                    amount=typed_date.amount,
                )
            )
        elif typed_date.kind == "anchor_calendar" and typed_date.unit:
            constraints.append(
                PhysicalDynamicDateRange(
                    stable_resource_id,
                    partition_key,
                    "anchor_calendar",
                    typed_date.unit,
                    month=typed_date.month,
                    day=typed_date.day,
                )
            )
        elif typed_date.kind == "calendar_range" and typed_date.start and typed_date.end:
            constraints.append(
                PhysicalBinary(
                    "and",
                    PhysicalComparison(">=", column, PhysicalLiteral(typed_date.start, TIME)),
                    PhysicalComparison("<=", column, PhysicalLiteral(typed_date.end, TIME)),
                    BOOLEAN,
                )
            )
        else:
            raise PhysicalPlanningError(
                "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED",
                f"typed date constraint is not materialized for scalar planning: {date}",
            )
    return tuple(constraints)


def _resolve_scope_atoms(expression, catalog: SecurityScopeCatalog, external_catalog):
    resolved = []
    for atom in expression.atoms:
        # These names are controlled compiler rules, not membership datasets.
        # Resolve them before catalog lookup so field collection does not reject
        # a scope that will be lowered to board ranges or instrument_rule.
        if atom in _DERIVED_SCOPE_MARKETS:
            resolved.append(("derived_market", atom))
            continue
        if atom == "当天买当天卖":
            resolved.append(("instrument_rule", atom))
            continue
        try:
            resolved.append(("security", catalog.resolve(atom)))
            continue
        except KeyError:
            pass
        try:
            resolved.append(("external", external_catalog.resolve(atom)))
        except KeyError as exc:
            raise PhysicalPlanningError(
                "PHYSICAL_SCOPE_DATA_UNAVAILABLE",
                f"scope membership is unavailable in official and external catalogs: {atom}",
            ) from exc
    return tuple(resolved)


def _scope_requires_security_join(expression) -> bool:
    if expression is None:
        return False
    catalog = current_security_scope_catalog()
    for atom in expression.atoms:
        try:
            catalog.resolve(atom)
        except KeyError:
            continue
        return True
    return False


def _lower_scope_expression(
    expression,
    catalog: SecurityScopeCatalog,
    external_catalog,
    anchor_resource_id: str,
):
    if isinstance(expression, ScopeAtom):
        derived_market = _DERIVED_SCOPE_MARKETS.get(expression.name)
        if derived_market is not None:
            return _lower_market_expression(
                parse_market_expression(derived_market), anchor_resource_id
            )
        if expression.name == "当天买当天卖":
            policy = current_external_data_policy().instrument_rule
            if policy is None:
                raise PhysicalPlanningError(
                    "PHYSICAL_INSTRUMENT_RULE_DATA_UNAVAILABLE",
                    "T+0 screening requires a versioned instrument rule dataset",
                )
            return PhysicalExternalExists(
                policy.resource_id,
                anchor_resource_id,
                (
                    ("snapshot_id", PhysicalLiteral(policy.snapshot_id, STRING)),
                    ("t0_eligible", PhysicalLiteral(True, BOOLEAN)),
                ),
            )
        try:
            resolved = catalog.resolve(expression.name)
        except KeyError:
            external = external_catalog.resolve(expression.name)
            policy = external.policy
            return PhysicalExternalExists(
                external_catalog.membership_resource_id,
                anchor_resource_id,
                (
                    ("scope_code", PhysicalLiteral(external.option.scope_code, STRING)),
                    ("snapshot_id", PhysicalLiteral(external.option.snapshot_id, STRING)),
                ),
                policy_id=policy.policy_id if policy is not None else None,
                policy_semantic_basis=(
                    policy.semantic_basis if policy is not None else None
                ),
                policy_risk_level=policy.risk_level if policy is not None else None,
                policy_rationale_urls=(
                    policy.rationale_urls if policy is not None else ()
                ),
            )
        else:
            name_predicate = PhysicalComparison(
                "=",
                PhysicalColumn("official_security", "name", STRING),
                PhysicalLiteral(resolved.name, STRING),
            )
            if not resolved.explicit_code:
                return name_predicate
            identity = resolved.identities[0]
            return PhysicalBinary(
                "and",
                name_predicate,
                PhysicalBinary(
                    "and",
                    PhysicalComparison(
                        "=",
                        PhysicalColumn("official_security", "mktcode", NUMERIC),
                        PhysicalLiteral(identity.mktcode, NUMERIC),
                    ),
                    PhysicalComparison(
                        "=",
                        PhysicalColumn("official_security", "tgtcode", STRING),
                        PhysicalLiteral(identity.tgtcode, STRING),
                    ),
                    BOOLEAN,
                ),
                BOOLEAN,
            )
    if isinstance(expression, ScopeNot):
        return PhysicalNot(
            _lower_scope_expression(
                expression.operand, catalog, external_catalog, anchor_resource_id
            )
        )
    if isinstance(expression, ScopeAnd):
        return PhysicalBinary(
            "and",
            _lower_scope_expression(
                expression.left, catalog, external_catalog, anchor_resource_id
            ),
            _lower_scope_expression(
                expression.right, catalog, external_catalog, anchor_resource_id
            ),
            BOOLEAN,
        )
    if isinstance(expression, ScopeOr):
        return PhysicalBinary(
            "or",
            _lower_scope_expression(
                expression.left, catalog, external_catalog, anchor_resource_id
            ),
            _lower_scope_expression(
                expression.right, catalog, external_catalog, anchor_resource_id
            ),
            BOOLEAN,
        )
    raise PhysicalPlanningError(
        "PHYSICAL_SCOPE_EXPRESSION_UNSUPPORTED",
        f"unsupported scope expression {type(expression).__name__}",
    )


_MARKET_CODES = {
    "深": (0,),
    "沪": (1,),
    "京": (103,),
    "沪深": (0, 1),
    "A股": (0, 1),
    "沪深京": (0, 1, 103),
}

_BOARD_PREFIXES = {
    "科创板": (1, ("688",)),
    "创业板": (0, ("300", "301")),
    "沪主板": (1, ("600", "601", "603", "605")),
    "深主板": (0, ("000", "001", "002", "003")),
}

_DERIVED_SCOPE_MARKETS = {
    "科创板注册制": "科创板",
    "沪深主板注册制": "沪主板|深主板",
}


def _lower_market_expression(expression, resource_id: str):
    union_codes = _union_market_codes(expression)
    if union_codes is not None:
        return PhysicalIn(
            PhysicalColumn(resource_id, "mktcode", NUMERIC),
            tuple(PhysicalLiteral(code, NUMERIC) for code in union_codes),
        )
    if isinstance(expression, MarketAtom):
        if expression.name in _MARKET_CODES:
            column = PhysicalColumn(resource_id, "mktcode", NUMERIC)
            return PhysicalIn(
                column,
                tuple(
                    PhysicalLiteral(code, NUMERIC)
                    for code in _MARKET_CODES[expression.name]
                ),
            )
        if expression.name in _BOARD_PREFIXES:
            market_code, prefixes = _BOARD_PREFIXES[expression.name]
            market = PhysicalIn(
                PhysicalColumn(resource_id, "mktcode", NUMERIC),
                (PhysicalLiteral(market_code, NUMERIC),),
            )
            ranges = tuple(
                PhysicalBinary(
                    "and",
                    PhysicalComparison(
                        ">=",
                        PhysicalColumn(resource_id, "tgtcode", STRING),
                        PhysicalLiteral(f"{prefix}000", STRING),
                    ),
                    PhysicalComparison(
                        "<=",
                        PhysicalColumn(resource_id, "tgtcode", STRING),
                        PhysicalLiteral(f"{prefix}999", STRING),
                    ),
                    BOOLEAN,
                )
                for prefix in prefixes
            )
            codes = ranges[0]
            for item in ranges[1:]:
                codes = PhysicalBinary("or", codes, item, BOOLEAN)
            return PhysicalBinary("and", market, codes, BOOLEAN)
        raise PhysicalPlanningError(
            "PHYSICAL_MARKET_DATA_UNAVAILABLE",
            f"official dataset does not contain market {expression.name}",
        )
    if isinstance(expression, MarketNot):
        return PhysicalNot(_lower_market_expression(expression.operand, resource_id))
    if isinstance(expression, MarketAnd):
        return PhysicalBinary(
            "and",
            _lower_market_expression(expression.left, resource_id),
            _lower_market_expression(expression.right, resource_id),
            BOOLEAN,
        )
    if isinstance(expression, MarketOr):
        return PhysicalBinary(
            "or",
            _lower_market_expression(expression.left, resource_id),
            _lower_market_expression(expression.right, resource_id),
            BOOLEAN,
        )
    raise PhysicalPlanningError(
        "PHYSICAL_MARKET_CONSTRAINT_UNSUPPORTED",
        f"unsupported typed market expression {type(expression).__name__}",
    )


def _union_market_codes(expression):
    if isinstance(expression, MarketAtom) and expression.name in _MARKET_CODES:
        return _MARKET_CODES[expression.name]
    if isinstance(expression, MarketOr):
        left = _union_market_codes(expression.left)
        right = _union_market_codes(expression.right)
        if left is not None and right is not None:
            return tuple(sorted(set((*left, *right))))
    return None
