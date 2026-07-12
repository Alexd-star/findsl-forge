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
from ..types import BOOLEAN, NUMERIC, STRING, TIME, OfficialType
from .catalog import PhysicalCatalog
from .expressions import PhysicalExpressionNode, PhysicalExpressionRegistry
from .ir import (
    PhysicalBinary,
    PhysicalAggregateGroup,
    PhysicalAggregateRef,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalCompositeAggregate,
    PhysicalCoalesce,
    PhysicalFilter,
    PhysicalGroupedAggregate,
    PhysicalIn,
    PhysicalJoin,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalNullIf,
    PhysicalNamedAggregate,
    PhysicalNot,
    PhysicalNthLatestValue,
    PhysicalPlan,
    PhysicalPrefixAverage,
    PhysicalRank,
    PhysicalRecentSessions,
    PhysicalScan,
    PhysicalTableScan,
    PhysicalTemporal,
    PhysicalTemporalWindow,
    PhysicalSetOperation,
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
    aggregate_calls = _aggregate_calls(lowering.plan)
    aggregate_contract = _aggregate_contract(lowering.plan, aggregate_calls)
    fields = _collect_fields(lowering.plan, catalog, expressions)
    resource_ids = tuple(sorted({field.resource_id for field in fields}))
    if not resource_ids:
        if _contains_universe_selector(lowering.plan):
            resource_ids = ("official_basic",)
        else:
            raise PhysicalPlanningError("PHYSICAL_PLAN_UNAVAILABLE", "logical plan has no directly mapped physical indicator")
    if aggregate_contract is not None:
        return _plan_grouped_aggregate(
            lowering.plan,
            aggregate_contract,
            catalog,
            fields,
            resource_ids,
            expressions,
            statistics,
        )
    if aggregate_calls:
        return _plan_composite_aggregate(
            lowering.plan,
            aggregate_calls,
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


@dataclass(frozen=True)
class _AggregateContract:
    call: CallExpr
    comparator: str
    bound: LiteralExpr
    function: str
    limit: Optional[Tuple[int, int]] = None


def _aggregate_calls(plan) -> Tuple[CallExpr, ...]:
    return tuple(
        call
        for expression in _logical_expressions(plan)
        for call in _walk_calls(expression)
        if call.binding is not None
        and str(call.binding.slots.get("agg_func", "")).strip()
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
        str(call.binding.slots.get("agg_func", "")).strip().upper()
        for call in calls
    }
    unsupported = sorted(functions - {"SUM", "AVG", "MAX", "MIN"})
    if unsupported:
        raise PhysicalPlanningError(
            "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
            f"aggregate function requires a dedicated contract: {', '.join(unsupported)}",
        )
    if len(calls) != 1:
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


def _plan_grouped_aggregate(
    logical_plan,
    contract: _AggregateContract,
    catalog: PhysicalCatalog,
    fields: Tuple[_ResolvedIndicator, ...],
    resource_ids: Tuple[str, ...],
    expressions: Optional[PhysicalExpressionRegistry],
    statistics: Optional[PhysicalStatisticsSnapshot],
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
    if field.direct_column is not None:
        measure = PhysicalColumn(
            field.resource_id,
            field.direct_column,
            _type_from_name(field.value_type),
        )
    else:
        assert field.expression is not None
        measure = _lower_declared_expression(field.expression, field.resource_id)
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
    decision = replace(
        _candidate_decision(resource, catalog, statistics),
        strategy_id="grouped_aggregate",
        selected=True,
    )
    return PhysicalPlanningResult(
        plan,
        selected,
        (decision,),
        "grouped_aggregate",
    )


def _plan_composite_aggregate(
    logical_plan,
    aggregate_calls: Tuple[CallExpr, ...],
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
    aggregate_resource_ids = set()
    for index, call in enumerate(unique_aggregates):
        function = str(call.binding.slots.get("agg_func", "")).strip().lower()
        if function not in {"sum", "avg", "max", "min"}:
            raise PhysicalPlanningError(
                "PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED",
                f"aggregate function requires a dedicated contract: {function.upper()}",
            )
        indicator_id = call.binding.slots.get("indicator_name", "")
        field = _field_for_indicator(fields, indicator_id)
        aggregate_resource_ids.add(field.resource_id)
        resource = catalog.resource(field.resource_id)
        aggregate_input: PhysicalPlan = PhysicalScan(
            field.resource_id,
            _scan_columns((field,)),
            None,
            resource.anchor_resource_id,
        )
        for constraint in _call_constraints(call, catalog, field.resource_id):
            aggregate_input = PhysicalFilter(aggregate_input, constraint)
        relation_alias = f"aggregate_{index}"
        measure_alias = f"metric_{index}"
        measure = PhysicalNamedAggregate(
            measure_alias,
            function,
            _physical_field_expression(field),
        )
        groups.append(PhysicalAggregateGroup(relation_alias, aggregate_input, (measure,)))
        refs[call.node_id] = PhysicalAggregateRef(
            relation_alias,
            measure_alias,
            _type_from_name(field.value_type),
        )

    scalar_calls = tuple(
        call for call in all_calls if call.node_id not in seen_aggregates
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
            raise PhysicalPlanningError(
                "PHYSICAL_APPROXIMATION_POLICY_MISSING",
                "approximate comparison requires catalog-provided tolerances",
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
    if _contains_temporal_plan(lowering.plan):
        raise PhysicalPlanningError(
            "PHYSICAL_TEMPORAL_MULTI_RESOURCE_UNSUPPORTED",
            "multi-resource temporal predicates require an explicit temporal join contract",
        )
    relation, root_id, joined = _build_join_relation(fields, resource_ids, catalog)
    plan = _lower_plan(
        lowering.plan,
        catalog,
        root_id,
        fields,
        base_plan=relation,
        allowed_resource_ids=frozenset(joined),
    )
    validate_physical_plan(plan, catalog, expressions)
    selected_resource = "+".join(joined)
    decision = PhysicalDecision(
        resource_id=selected_resource,
        feasible=True,
        cost=float(sum(catalog.resource(item).priority for item in joined)),
        estimated=True,
        reason_code="PHYSICAL_STABLE_JOIN_SELECTED",
        reason="left-deep same-entity join on catalog-declared stable keys",
        strategy_id="stable_key_join",
        selected=True,
    )
    return PhysicalPlanningResult(plan, selected_resource, (decision,), "stable_key_join")


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
            if _is_universe_call(call):
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
    current = plan
    while isinstance(current, (LogicalFilter, LogicalLimit, LogicalRank, LogicalStage, LogicalConsecutive, LogicalExist)):
        if isinstance(current, LogicalFilter):
            yield current.predicate
        elif isinstance(current, (LogicalConsecutive, LogicalExist)):
            yield current.spec.predicate
        elif isinstance(current, LogicalRank):
            yield current.order_by
        current = current.operation if isinstance(current, LogicalStage) else current.input


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
    ignored = {
        slot: value
        for slot, value in call.binding.slots.items()
        if slot not in {"indicator_name", "market", "date", "direction", "agg_func"} and str(value).strip()
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
        if isinstance(input_plan, PhysicalRank):
            raise PhysicalPlanningError(
                "PHYSICAL_CHAINED_RANK_UNSUPPORTED",
                "chained rank requires explicit stage-output alias propagation",
            )
        for constraint in _call_constraints(plan.order_by, catalog, resource_id):
            input_plan = PhysicalFilter(input_plan, constraint)
        expression = _lower_expr(plan.order_by, catalog, resource_id, fields, allow_rank=True, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids)
        if (
            isinstance(plan.bound, LiteralExpr)
            and isinstance(plan.bound.value, str)
            and plan.bound.value.endswith("%")
        ):
            raise PhysicalPlanningError(
                "PHYSICAL_RANK_BOUND_UNSUPPORTED",
                "percentage rank bounds require partition-cardinality lowering",
            )
        bound = _lower_expr(plan.bound, catalog, resource_id, fields, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids)
        if not isinstance(bound, PhysicalLiteral) or not isinstance(bound.value, (int, float)):
            raise PhysicalPlanningError("PHYSICAL_RANK_BOUND_UNSUPPORTED", "physical rank requires a numeric literal bound")
        return PhysicalRank(input_plan, expression, plan.direction, bound, plan.comparator)
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
        if expression.node_id in seen:
            continue
        seen.add(expression.node_id)
        unique.append(expression)
    result = unique[0]
    for expression in unique[1:]:
        result = PhysicalBinary("and", result, expression, BOOLEAN)
    return result


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
    allowed_resource_ids=None,
):
    if isinstance(expression, LiteralExpr):
        return _physical_literal(expression)
    if isinstance(expression, CallExpr):
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
        if field.direct_column is not None:
            return PhysicalColumn(field.resource_id, field.direct_column, _type_from_name(field.value_type))
        assert field.expression is not None
        return _lower_declared_expression(field.expression, field.resource_id)
    if isinstance(expression, BinaryExpr):
        return PhysicalBinary(
            expression.op,
            _lower_expr(expression.left, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
            _lower_expr(expression.right, catalog, resource_id, fields, allow_rank=allow_rank, expression_overrides=expression_overrides, allowed_resource_ids=allowed_resource_ids),
            expression.type,
        )
    if isinstance(expression, ComparisonExpr):
        if expression.op == "~=":
            raise PhysicalPlanningError(
                "PHYSICAL_APPROXIMATION_POLICY_MISSING",
                "approximate comparison requires catalog-provided absolute and relative tolerances",
            )
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
