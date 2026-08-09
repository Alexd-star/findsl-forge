from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlglot import exp

from ..physical.catalog import PhysicalCatalog
from ..physical.runtime import current_semantic_policy
from ..physical.ir import (
    PhysicalAbs,
    PhysicalBinary,
    PhysicalAggregateGroup,
    PhysicalAggregateRank,
    PhysicalAggregateRef,
    PhysicalCoalesce,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalCandidateSetOperation,
    PhysicalCompositeAggregate,
    PhysicalFilter,
    PhysicalDynamicDateRange,
    PhysicalEventFilter,
    PhysicalEventProjection,
    PhysicalEventRef,
    PhysicalExternalExists,
    PhysicalExtreme,
    PhysicalGroupedAggregate,
    PhysicalGreatest,
    PhysicalIn,
    PhysicalJoin,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalNullIf,
    PhysicalNamedRank,
    PhysicalNot,
    PhysicalNthLatestValue,
    PhysicalPlan,
    PhysicalPrefixAverage,
    PhysicalPrefixAggregate,
    PhysicalPrefixJoin,
    PhysicalPrefixRef,
    PhysicalPattern,
    PhysicalPosition,
    PhysicalProjectedRef,
    PhysicalRank,
    PhysicalRankExpression,
    PhysicalRecentSessions,
    PhysicalScan,
    PhysicalSessionBoundaryRange,
    PhysicalTableScan,
    PhysicalStageRank,
    PhysicalSetOperation,
    PhysicalTemporal,
    PhysicalTemporalAggregate,
    PhysicalTemporalRank,
    PhysicalUnary,
)
from ..physical.validate import validate_physical_plan
from .validation import DorisAstValidation, validate_doris_ast


class DorisBackendError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DorisRenderResult:
    ast: exp.Select
    sql: str
    round_trip_stable: bool
    validation: object
    ast_validation: DorisAstValidation


_BINARY = {
    "+": exp.Add,
    "-": exp.Sub,
    "*": exp.Mul,
    "/": exp.Div,
    "&": exp.And,
    "and": exp.And,
    "|": exp.Or,
    "or": exp.Or,
    "^": exp.Xor,
    "xor": exp.Xor,
}

_COMPARISON = {
    "=": exp.EQ,
    "==": exp.EQ,
    "!=": exp.NEQ,
    "<>": exp.NEQ,
    ">": exp.GT,
    ">=": exp.GTE,
    "<": exp.LT,
    "<=": exp.LTE,
}


def render_doris(plan: PhysicalPlan, catalog: PhysicalCatalog, expressions=None) -> DorisRenderResult:
    validate_physical_plan(plan, catalog, expressions)
    ast = _render_plan(plan, catalog)
    sql = ast.sql(dialect="doris")
    validation = validate_doris_ast(sql, catalog)
    if not validation.passed:
        raise DorisBackendError("DORIS_AST_VALIDATION_FAILED", ", ".join(validation.issues))
    return DorisRenderResult(ast, sql, validation.round_trip_stable, validation.safety, validation)


def _render_plan(
    plan: PhysicalPlan,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    if isinstance(plan, PhysicalJoin):
        return _render_join(plan, catalog)
    if isinstance(plan, PhysicalTableScan):
        resource = catalog.resource(plan.resource_id)
        alias = plan.resource_id
        projections = tuple(
            exp.column(name, table=alias, quoted=True)
            for name in resource.stable_keys
        )
        query = exp.select(*projections).from_(
            exp.table_(resource.table, db=resource.database, quoted=True, alias=alias)
        )
        if plan.partition_predicate is not None:
            query = query.where(_render_expr(plan.partition_predicate, catalog, plan))
        return query
    if isinstance(plan, PhysicalScan):
        resource = catalog.resource(plan.resource_id)
        anchor = catalog.resource(plan.anchor_resource_id) if plan.anchor_resource_id else None
        projections = tuple(
            exp.column(
                name,
                table="anchor" if anchor is not None else "q",
                quoted=True,
            )
            for name in ("mktcode", "tgtcode", "bizdate")
        )
        resource_table = exp.table_(resource.table, db=resource.database, quoted=True, alias="q")
        query = exp.select(*projections)
        if anchor is not None:
            join_keys = tuple(key for key in resource.stable_keys if key in anchor.stable_keys)
            if not join_keys:
                raise DorisBackendError(
                    "DORIS_ANCHOR_JOIN_UNAVAILABLE",
                    f"resource {resource.resource_id} has no stable join key with {anchor.resource_id}",
                )
            predicate = exp.and_(
                *(
                    exp.EQ(
                        this=exp.column(key, table="q", quoted=True),
                        expression=exp.column(key, table="anchor", quoted=True),
                    )
                    for key in join_keys
                )
            )
            anchor_table = exp.table_(anchor.table, db=anchor.database, quoted=True, alias="anchor")
            query = query.from_(anchor_table).join(resource_table, on=predicate, join_type="LEFT")
        else:
            query = query.from_(resource_table)
        if plan.partition_predicate is not None:
            query = query.where(_render_expr(plan.partition_predicate, catalog, plan))
        return query
    if isinstance(plan, PhysicalPrefixAggregate):
        return _render_prefix_aggregate(plan, catalog)
    if isinstance(plan, PhysicalFilter):
        return _render_plan(plan.input, catalog, cte_prefix).where(
            _render_expr(plan.predicate, catalog, _find_relation(plan.input))
        )
    if isinstance(plan, PhysicalLimit):
        count = (
            plan.count
            if plan.count is not None
            else 9223372036854775807 - plan.offset
        )
        query = _render_plan(plan.input, catalog, cte_prefix)
        if query.args.get("order") is None:
            query = query.order_by(
                *(exp.column(key, quoted=True) for key in ("mktcode", "tgtcode", "bizdate"))
            )
        query = query.limit(count)
        return query.offset(plan.offset) if plan.offset else query
    if isinstance(plan, PhysicalRank):
        inner = _render_plan(plan.input, catalog, cte_prefix)
        relation = _find_relation(plan.input)
        stable_alias = _stable_alias(relation)
        metric = (
            None
            if isinstance(plan.expression, PhysicalLiteral)
            else _render_expr(plan.expression, catalog, relation)
        )
        order = _rank_order(metric, plan.direction == "desc", stable_alias)
        window = exp.Window(
            this=_rank_function(),
            partition_by=[exp.column("bizdate", table=stable_alias, quoted=True)],
            order=order,
        ).as_("__rank_value")
        inner = inner.select(window, append=True)
        if plan.percentage:
            inner = inner.select(
                exp.Window(
                    this=exp.Count(this=exp.Star()),
                    partition_by=[exp.column("bizdate", table=stable_alias, quoted=True)],
                ).as_("__partition_count"),
                append=True,
            )
        ranked = inner.subquery(alias="ranked")
        outer = exp.select(
            *(exp.column(name, table="ranked", quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
        ).from_(ranked)
        comparator = _render_bounded_comparison(
            exp.column("__rank_value", table="ranked", quoted=True),
            plan.comparator,
            _render_rank_bound(plan.bound, plan.percentage, "ranked"),
            (
                _render_rank_bound(plan.upper_bound, plan.percentage, "ranked")
                if plan.upper_bound is not None
                else None
            ),
            plan.lower_inclusive,
            plan.upper_inclusive,
        )
        return outer.where(comparator)
    if isinstance(plan, PhysicalAggregateRank):
        return _render_aggregate_rank(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalGroupedAggregate):
        return _render_grouped_aggregate(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalCompositeAggregate):
        return _render_composite_aggregate(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalEventFilter):
        return _render_event_filter(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalEventProjection):
        return _render_event_projection(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalTemporal):
        return _render_temporal(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalTemporalAggregate):
        return _render_temporal_aggregate(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalTemporalRank):
        return _render_temporal_aggregate(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalRankExpression):
        return _render_rank_expression(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalStageRank):
        return _render_stage_rank(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalSetOperation):
        return _render_set_operation(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalCandidateSetOperation):
        return _render_candidate_set_operation(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalPrefixJoin):
        return _render_prefix_join(plan, catalog, cte_prefix)
    raise DorisBackendError("DORIS_PLAN_UNSUPPORTED", f"unsupported physical node {type(plan).__name__}")


def _render_event_filter(
    plan: PhysicalEventFilter,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
    source = _append_event_columns(
        source,
        plan.events,
        plan.projections,
        catalog,
        relation,
    )

    alias = "event_rows"
    rows = source.subquery(alias=alias)
    if plan.quantifier == "none":
        return _render_event_absence(plan, rows, relation, catalog)
    outer = exp.select(
        *(exp.column(name, table=alias, quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
    ).from_(rows)
    predicate = _retarget_event_result_columns(
        _render_expr(plan.predicate, catalog), alias, catalog
    )
    for constraint in plan.result_constraints:
        rendered = _render_expr(constraint, catalog, relation)
        predicate = exp.and_(
            predicate,
            _retarget_event_result_columns(rendered, alias, catalog),
        )
    return outer.where(predicate)


def _append_event_columns(
    source: exp.Select,
    events,
    projections,
    catalog: PhysicalCatalog,
    relation,
) -> exp.Select:
    stable_alias = _stable_alias(relation)
    partition = [
        exp.column("mktcode", table=stable_alias, quoted=True),
        exp.column("tgtcode", table=stable_alias, quoted=True),
    ]
    order = exp.Order(
        expressions=[
            exp.Ordered(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                desc=False,
                nulls_first=True,
            )
        ]
    )

    for event in events:
        if isinstance(event, PhysicalPattern):
            source = source.select(
                _render_expr(event.predicate, catalog, relation).as_(
                    event.alias,
                    quoted=True,
                ),
                append=True,
            )
            continue
        if isinstance(event, PhysicalExtreme):
            value = _render_expr(event.expression, catalog, relation)
            aggregate = exp.Max if event.direction == "high" else exp.Min
            extreme = _event_window_aggregate(
                value,
                aggregate,
                partition,
                order,
                event.lookback_sessions,
            )
            comparator = exp.GTE if event.direction == "high" else exp.LTE
            source = source.select(
                comparator(this=value, expression=extreme).as_(event.alias, quoted=True),
                append=True,
            )
            continue
        if isinstance(event, PhysicalPosition):
            value = _render_expr(event.expression, catalog, relation)
            minimum = _event_window_aggregate(
                value,
                exp.Min,
                partition,
                order,
                event.lookback_sessions,
            )
            maximum = _event_window_aggregate(
                value,
                exp.Max,
                partition,
                order,
                event.lookback_sessions,
            )
            missing = exp.or_(
                exp.Is(this=value.copy(), expression=exp.Null()),
                exp.or_(
                    exp.Is(this=minimum.copy(), expression=exp.Null()),
                    exp.Is(this=maximum.copy(), expression=exp.Null()),
                ),
            )
            ratio = exp.Div(
                this=exp.Paren(
                    this=exp.Sub(this=value.copy(), expression=minimum.copy())
                ),
                expression=exp.Nullif(
                    this=exp.Sub(this=maximum.copy(), expression=minimum.copy()),
                    expression=exp.convert(0),
                ),
            )
            position = exp.Case(
                ifs=[
                    exp.If(this=missing, true=exp.Null()),
                    exp.If(this=exp.LTE(this=value.copy(), expression=minimum.copy()), true=exp.convert("最低")),
                    exp.If(this=exp.GTE(this=value.copy(), expression=maximum.copy()), true=exp.convert("最高")),
                    exp.If(this=exp.LTE(this=ratio.copy(), expression=exp.convert(0.25)), true=exp.convert("低")),
                    exp.If(this=exp.GTE(this=ratio, expression=exp.convert(0.75)), true=exp.convert("高")),
                ],
                default=exp.convert("中"),
            )
            source = source.select(position.as_(event.alias, quoted=True), append=True)
            continue
        left = _render_expr(event.left, catalog, relation)
        right = _render_expr(event.right, catalog, relation)
        previous_left = exp.Window(
            this=exp.Lag(this=left.copy()),
            partition_by=[item.copy() for item in partition],
            order=order.copy(),
        )
        previous_right = exp.Window(
            this=exp.Lag(this=right.copy()),
            partition_by=[item.copy() for item in partition],
            order=order.copy(),
        )
        if event.direction == "above":
            current = exp.GT(this=left, expression=right)
            previous = exp.LTE(this=previous_left, expression=previous_right)
        else:
            current = exp.LT(this=left, expression=right)
            previous = exp.GTE(this=previous_left, expression=previous_right)
        source = source.select(
            exp.and_(current, previous).as_(event.alias, quoted=True),
            append=True,
        )

    for projection in projections:
        source = source.select(
            _render_expr(projection.expression, catalog, relation).as_(
                projection.alias,
                quoted=True,
            ),
            append=True,
        )

    return source


def _render_prefix_join(
    plan: PhysicalPrefixJoin,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    anchor_name = f"{cte_prefix}prefix_anchor_rows"
    values_name = f"{cte_prefix}prefix_values"
    anchor_alias = "prefix_anchor"
    anchor = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
    passthrough = _prefix_passthrough_columns(plan.input)
    for column in passthrough:
        anchor = anchor.select(
            _render_expr(column, catalog, relation).as_(column.column, quoted=True),
            append=True,
        )
    values = exp.select(
        *(
            exp.column(key, table=anchor_alias, quoted=True)
            for key in ("mktcode", "tgtcode", "bizdate")
        ),
        *(
            exp.column(column.column, table=anchor_alias, quoted=True)
            for column in passthrough
        ),
    ).from_(exp.table_(anchor_name, alias=anchor_alias, quoted=True))

    for index, projection in enumerate(plan.projections):
        expression = projection.expression
        if not isinstance(expression, PhysicalPrefixAverage):
            raise DorisBackendError(
                "DORIS_PREFIX_PROJECTION_UNSUPPORTED",
                "prefix join projections must be prefix averages",
            )
        resource = catalog.resource(expression.resource_id)
        current_alias = f"prefix_current_{index}"
        previous_alias = f"prefix_previous_{index}"
        current = exp.table_(
            resource.table,
            db=resource.database,
            quoted=True,
            alias=current_alias,
        )
        previous = exp.table_(
            resource.table,
            db=resource.database,
            quoted=True,
            alias=previous_alias,
        )
        current_join = exp.and_(
            *(
                exp.EQ(
                    this=exp.column(key, table=current_alias, quoted=True),
                    expression=exp.column(key, table=anchor_alias, quoted=True),
                )
                for key in ("mktcode", "tgtcode", "bizdate")
            )
        )
        previous_join = exp.and_(
            exp.EQ(
                this=exp.column("mktcode", table=previous_alias, quoted=True),
                expression=exp.column("mktcode", table=current_alias, quoted=True),
            ),
            exp.EQ(
                this=exp.column("tgtcode", table=previous_alias, quoted=True),
                expression=exp.column("tgtcode", table=current_alias, quoted=True),
            ),
            exp.EQ(
                this=exp.column("row_no", table=previous_alias, quoted=True),
                expression=exp.Sub(
                    this=exp.column("row_no", table=current_alias, quoted=True),
                    expression=exp.convert(expression.window),
                ),
            ),
        )
        average = _prefix_average_expression(
            expression,
            current_alias,
            previous_alias,
        )
        values = values.join(current, on=current_join, join_type="INNER")
        values = values.join(previous, on=previous_join, join_type="LEFT")
        values = values.select(
            average.as_(projection.alias, quoted=True),
            append=True,
        )

    result = (
        exp.select(
            *(
                exp.column(key, table=values_name, quoted=True)
                for key in ("mktcode", "tgtcode", "bizdate")
            ),
            *(
                exp.column(column.column, table=values_name, quoted=True)
                for column in passthrough
            ),
            *(
                exp.column(projection.alias, table=values_name, quoted=True)
                for projection in plan.projections
            ),
        )
        .from_(exp.table_(values_name, quoted=True))
        .with_(anchor_name, as_=anchor)
        .with_(values_name, as_=values)
    )
    if plan.predicate is not None:
        result = result.where(_render_expr(plan.predicate, catalog))
    return result


def _prefix_passthrough_columns(plan: PhysicalPlan):
    columns = {}

    def visit(node):
        if isinstance(node, (PhysicalScan, PhysicalTableScan)):
            for column in node.columns:
                if column.column not in {"mktcode", "tgtcode", "bizdate"}:
                    columns.setdefault(column.column, column)
            return
        if isinstance(node, PhysicalJoin):
            visit(node.left)
            visit(node.right)

    visit(plan)
    return tuple(columns[key] for key in sorted(columns))


def _prefix_average_expression(
    expression: PhysicalPrefixAverage,
    current_alias: str,
    previous_alias: str,
):
    sum_delta = exp.Sub(
        this=exp.column(expression.sum_column, table=current_alias, quoted=True),
        expression=exp.Coalesce(
            this=exp.column(expression.sum_column, table=previous_alias, quoted=True),
            expressions=[exp.convert(0)],
        ),
    )
    count_delta = exp.Sub(
        this=exp.column(expression.count_column, table=current_alias, quoted=True),
        expression=exp.Coalesce(
            this=exp.column(expression.count_column, table=previous_alias, quoted=True),
            expressions=[exp.convert(0)],
        ),
    )
    average = exp.Div(
        this=exp.Mul(this=exp.Paren(this=sum_delta), expression=exp.convert(1.0)),
        expression=exp.Nullif(this=count_delta, expression=exp.convert(0)),
    )
    if expression.scale_divisor != 1.0:
        average = exp.Div(
            this=average,
            expression=exp.convert(expression.scale_divisor),
        )
    return average


def _render_event_projection(
    plan: PhysicalEventProjection,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
    source = _append_event_columns(
        source,
        plan.events,
        plan.projections,
        catalog,
        relation,
    )
    alias = "event_rows"
    rows = source.subquery(alias=alias)
    return exp.select(
        *(
            exp.column(name, table=alias, quoted=True)
            for name in (
                "mktcode",
                "tgtcode",
                "bizdate",
                *(event.alias for event in plan.events),
                *(projection.alias for projection in plan.projections),
            )
        )
    ).from_(rows)


def _render_event_absence(
    plan: PhysicalEventFilter,
    rows: exp.Subquery,
    relation,
    catalog: PhysicalCatalog,
) -> exp.Select:
    keys = ("mktcode", "tgtcode")
    eligibility = _render_expr(plan.eligibility_predicate, catalog)
    occurred = _render_expr(plan.predicate, catalog)
    for constraint in plan.result_constraints:
        rendered = _retarget_event_result_columns(
            _render_expr(constraint, catalog, relation),
            "event_rows",
            catalog,
        )
        eligibility = exp.and_(eligibility, rendered.copy())
        occurred = exp.and_(occurred, rendered)
    eligible_count = exp.Max(
        this=exp.Case(
            ifs=[exp.If(this=eligibility, true=exp.convert(1))],
            default=exp.convert(0),
        )
    )
    occurred_count = exp.Max(
        this=exp.Case(
            ifs=[exp.If(this=occurred, true=exp.convert(1))],
            default=exp.convert(0),
        )
    )
    qualified = (
        exp.select(
            *(exp.column(key, table="event_rows", quoted=True) for key in keys)
        )
        .from_(rows)
        .group_by(
            *(exp.column(key, table="event_rows", quoted=True) for key in keys)
        )
        .having(
            exp.and_(
                exp.EQ(this=eligible_count, expression=exp.convert(1)),
                exp.EQ(this=occurred_count, expression=exp.convert(0)),
            )
        )
    )
    candidate_alias = "event_absence_keys"
    anchor_alias = "event_absence_anchor"
    latest_alias = "event_absence_latest"
    anchor = catalog.resource(plan.anchor_resource_id)
    latest = exp.select(
        exp.Max(
            this=exp.column(anchor.partition_key, table=latest_alias, quoted=True)
        )
    ).from_(
        exp.table_(
            anchor.table,
            db=anchor.database,
            quoted=True,
            alias=latest_alias,
        )
    )
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(key, table=anchor_alias, quoted=True),
                expression=exp.column(key, table=candidate_alias, quoted=True),
            )
            for key in keys
        )
    )
    return (
        exp.select(
            *(
                exp.column(key, table=anchor_alias, quoted=True)
                for key in (*keys, "bizdate")
            )
        )
        .from_(
            exp.table_(
                anchor.table,
                db=anchor.database,
                quoted=True,
                alias=anchor_alias,
            )
        )
        .join(
            qualified.subquery(alias=candidate_alias),
            on=join_predicate,
            join_type="INNER",
        )
        .where(
            exp.EQ(
                this=exp.column(
                    anchor.partition_key,
                    table=anchor_alias,
                    quoted=True,
                ),
                expression=exp.Subquery(this=latest),
            )
        )
    )


def _event_window_aggregate(value, aggregate, partition, order, lookback_sessions):
    if lookback_sessions == 1:
        frame = exp.WindowSpec(
            kind="ROWS",
            start="CURRENT ROW",
            end="CURRENT ROW",
        )
    else:
        frame_start = (
            "UNBOUNDED"
            if lookback_sessions is None
            else exp.Literal.number(lookback_sessions - 1)
        )
        frame = exp.WindowSpec(
            kind="ROWS",
            start=frame_start,
            start_side="PRECEDING",
            end="CURRENT ROW",
        )
    return exp.Window(
        this=aggregate(this=value.copy()),
        partition_by=[item.copy() for item in partition],
        order=order.copy(),
        spec=frame,
    )


def _render_set_aggregate(function: str, value, date):
    simple = {
        "sum": exp.Sum,
        "avg": exp.Avg,
        "max": exp.Max,
        "min": exp.Min,
    }
    if function in simple:
        return simple[function](this=value)
    if function not in {"growth_rise", "growth_fall"}:
        raise DorisBackendError(
            "DORIS_AGGREGATE_UNSUPPORTED",
            f"unsupported set aggregate function {function}",
        )
    first = exp.func("MIN_BY", value.copy(), date.copy())
    last = exp.func("MAX_BY", value.copy(), date.copy())
    delta = (
        exp.Sub(this=last, expression=first.copy())
        if function == "growth_rise"
        else exp.Sub(this=first.copy(), expression=last)
    )
    return exp.Div(
        this=exp.Mul(this=exp.Paren(this=delta), expression=exp.convert(100)),
        expression=exp.Nullif(
            this=exp.Abs(this=first),
            expression=exp.convert(0),
        ),
    )
def _retarget_event_result_columns(expression, alias: str, catalog: PhysicalCatalog):
    resource_aliases = {resource.resource_id for resource in catalog.resources}
    resource_aliases.update({"q", "anchor", "prefix_values"})
    stable_names = {"mktcode", "tgtcode", "bizdate"}

    def replace(node):
        if isinstance(node, exp.Column) and node.name in stable_names and node.table in resource_aliases:
            return exp.column(node.name, table=alias, quoted=True)
        return node

    return expression.transform(replace)


def _render_grouped_aggregate(
    plan: PhysicalGroupedAggregate,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
    stable_alias = _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    aggregate = _render_set_aggregate(
        plan.function,
        _render_expr(plan.measure, catalog, relation),
        exp.column("bizdate", table=stable_alias, quoted=True),
    ).as_("metric_value", quoted=True)
    source.set(
        "expressions",
        [
            *(exp.column(key, table=stable_alias, quoted=True) for key in keys),
            aggregate,
        ],
    )
    source = source.group_by(
        *(exp.column(key, table=stable_alias, quoted=True) for key in keys)
    )
    aggregate_rows = source.subquery(alias="aggregate_rows")
    qualified = exp.select(
        *(exp.column(key, table="aggregate_rows", quoted=True) for key in keys)
    ).from_(aggregate_rows).where(
        _COMPARISON[plan.comparator](
            this=exp.column("metric_value", table="aggregate_rows", quoted=True),
            expression=_render_expr(plan.bound, catalog, relation),
        )
    )
    qualified_rows = qualified.subquery(alias="qualified_result")
    anchor = catalog.resource(plan.anchor_resource_id)
    anchor_table = exp.table_(
        anchor.table,
        db=anchor.database,
        quoted=True,
        alias="anchor_out",
    )
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(key, table="anchor_out", quoted=True),
                expression=exp.column(key, table="qualified_result", quoted=True),
            )
            for key in keys
        )
    )
    latest_table = exp.table_(
        anchor.table,
        db=anchor.database,
        quoted=True,
        alias="latest_anchor",
    )
    latest = exp.Subquery(
        this=exp.select(
            exp.Max(
                this=exp.column(anchor.partition_key, table="latest_anchor", quoted=True)
            )
        ).from_(latest_table)
    )
    return (
        exp.select(
            *(exp.column(key, table="anchor_out", quoted=True) for key in (*keys, "bizdate"))
        )
        .from_(anchor_table)
        .join(qualified_rows, on=join_predicate, join_type="INNER")
        .where(
            exp.EQ(
                this=exp.column(anchor.partition_key, table="anchor_out", quoted=True),
                expression=latest,
            )
        )
    )


def _render_prefix_aggregate(
    plan: PhysicalPrefixAggregate,
    catalog: PhysicalCatalog,
) -> exp.Select:
    resource = catalog.resource(plan.resource_id)
    anchor = catalog.resource(plan.anchor_resource_id)
    current_alias = "q"
    previous_alias = "prefix_previous"
    anchor_alias = "anchor"
    current = exp.table_(
        resource.table,
        db=resource.database,
        quoted=True,
        alias=current_alias,
    )
    previous = exp.table_(
        resource.table,
        db=resource.database,
        quoted=True,
        alias=previous_alias,
    )
    anchor_table = exp.table_(
        anchor.table,
        db=anchor.database,
        quoted=True,
        alias=anchor_alias,
    )
    current_join = exp.and_(
        *(
            exp.EQ(
                this=exp.column(key, table=current_alias, quoted=True),
                expression=exp.column(key, table=anchor_alias, quoted=True),
            )
            for key in ("mktcode", "tgtcode", "bizdate")
        )
    )
    previous_join = exp.and_(
        exp.EQ(
            this=exp.column("mktcode", table=previous_alias, quoted=True),
            expression=exp.column("mktcode", table=current_alias, quoted=True),
        ),
        exp.EQ(
            this=exp.column("tgtcode", table=previous_alias, quoted=True),
            expression=exp.column("tgtcode", table=current_alias, quoted=True),
        ),
        exp.EQ(
            this=exp.column("row_no", table=previous_alias, quoted=True),
            expression=exp.Sub(
                this=exp.column("row_no", table=current_alias, quoted=True),
                expression=exp.convert(plan.window),
            ),
        ),
    )
    sum_delta = exp.column(plan.sum_column, table=current_alias, quoted=True)
    if not plan.full_history:
        sum_delta = exp.Sub(
            this=sum_delta,
            expression=exp.Coalesce(
                this=exp.column(plan.sum_column, table=previous_alias, quoted=True),
                expressions=[exp.convert(0)],
            ),
        )
    metric = sum_delta
    if plan.function == "AVG":
        count_delta = exp.column(
            plan.count_column,
            table=current_alias,
            quoted=True,
        )
        if not plan.full_history:
            count_delta = exp.Sub(
                this=count_delta,
                expression=exp.Coalesce(
                    this=exp.column(
                        plan.count_column,
                        table=previous_alias,
                        quoted=True,
                    ),
                    expressions=[exp.convert(0)],
                ),
            )
        metric = exp.Div(
            this=exp.Mul(this=exp.Paren(this=sum_delta), expression=exp.convert(1.0)),
            expression=exp.Nullif(this=count_delta, expression=exp.convert(0)),
        )
    if plan.scale_divisor != 1.0:
        metric = exp.Div(
            this=exp.Paren(this=metric),
            expression=exp.convert(plan.scale_divisor),
        )
    latest = exp.convert(plan.as_of_date) if plan.full_history else exp.Subquery(
        this=exp.select(
            exp.Max(
                this=exp.column(
                    anchor.partition_key,
                    table="latest_anchor",
                    quoted=True,
                )
            )
        ).from_(
            exp.table_(
                anchor.table,
                db=anchor.database,
                quoted=True,
                alias="latest_anchor",
            )
        )
    )
    predicate = _COMPARISON[plan.comparator](
        this=metric,
        expression=exp.convert(plan.bound.value),
    )
    date_alias = current_alias if plan.full_history else anchor_alias
    predicate = exp.and_(
        exp.EQ(
            this=exp.column(anchor.partition_key, table=date_alias, quoted=True),
            expression=latest,
        ),
        predicate,
    )
    scan_context = PhysicalScan(
        plan.resource_id,
        (),
        None,
        plan.anchor_resource_id,
    )
    for constraint in plan.constraints:
        predicate = exp.and_(
            predicate,
            _render_expr(constraint, catalog, scan_context),
        )
    if plan.full_history:
        return exp.select(
            *(
                exp.column(key, table=current_alias, quoted=True)
                for key in ("mktcode", "tgtcode", "bizdate")
            )
        ).from_(current).where(predicate)
    return (
        exp.select(
            *(
                exp.column(key, table=anchor_alias, quoted=True)
                for key in ("mktcode", "tgtcode", "bizdate")
            )
        )
        .from_(anchor_table)
        .join(current, on=current_join, join_type="INNER")
        .join(previous, on=previous_join, join_type="LEFT")
        .where(predicate)
    )


def _render_aggregate_rank(
    plan: PhysicalAggregateRank,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
    stable_alias = _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    aggregate = _render_set_aggregate(
        plan.function,
        _render_expr(plan.measure, catalog, relation),
        exp.column("bizdate", table=stable_alias, quoted=True),
    ).as_("metric_value", quoted=True)
    source.set(
        "expressions",
        [
            *(exp.column(key, table=stable_alias, quoted=True) for key in keys),
            aggregate,
        ],
    )
    source = source.group_by(
        *(exp.column(key, table=stable_alias, quoted=True) for key in keys)
    )
    aggregate_rows = source.subquery(alias="aggregate_rows")
    order = _rank_order(
        exp.column("metric_value", table="aggregate_rows", quoted=True),
        plan.direction == "desc",
        "aggregate_rows",
    )
    ranked = exp.select(
        *(exp.column(key, table="aggregate_rows", quoted=True) for key in keys),
        exp.column("metric_value", table="aggregate_rows", quoted=True),
        exp.Window(this=_rank_function(), order=order).as_("__rank_value"),
    ).from_(aggregate_rows)
    if plan.percentage:
        ranked = ranked.select(
            exp.Window(this=exp.Count(this=exp.Star())).as_("__partition_count"),
            append=True,
        )
    aggregate_ranked = ranked.subquery(alias="aggregate_ranked")
    qualified = exp.select(
        *(exp.column(key, table="aggregate_ranked", quoted=True) for key in keys)
    ).from_(aggregate_ranked).where(
        _render_bounded_comparison(
            exp.column("__rank_value", table="aggregate_ranked", quoted=True),
            plan.comparator,
            _render_rank_bound(
                plan.bound,
                plan.percentage,
                "aggregate_ranked",
            ),
            (
                _render_rank_bound(
                    plan.upper_bound,
                    plan.percentage,
                    "aggregate_ranked",
                )
                if plan.upper_bound is not None
                else None
            ),
            plan.lower_inclusive,
            plan.upper_inclusive,
        )
    )
    qualified_rows = qualified.subquery(alias="qualified_rank")
    anchor = catalog.resource(plan.anchor_resource_id)
    anchor_table = exp.table_(
        anchor.table,
        db=anchor.database,
        quoted=True,
        alias="rank_anchor",
    )
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(key, table="rank_anchor", quoted=True),
                expression=exp.column(key, table="qualified_rank", quoted=True),
            )
            for key in keys
        )
    )
    latest = exp.Subquery(
        this=exp.select(
            exp.Max(
                this=exp.column(
                    anchor.partition_key,
                    table="latest_rank_anchor",
                    quoted=True,
                )
            )
        ).from_(
            exp.table_(
                anchor.table,
                db=anchor.database,
                quoted=True,
                alias="latest_rank_anchor",
            )
        )
    )
    return (
        exp.select(
            *(
                exp.column(key, table="rank_anchor", quoted=True)
                for key in (*keys, "bizdate")
            )
        )
        .from_(anchor_table)
        .join(qualified_rows, on=join_predicate, join_type="INNER")
        .where(
            exp.EQ(
                this=exp.column(
                    anchor.partition_key,
                    table="rank_anchor",
                    quoted=True,
                ),
                expression=latest,
            )
        )
    )


def _render_rank_bound(bound, percentage: bool, table_alias: str):
    if not percentage:
        return exp.convert(bound.value)
    return exp.Ceil(
        this=exp.Div(
            this=exp.Mul(
                this=exp.column(
                    "__partition_count",
                    table=table_alias,
                    quoted=True,
                ),
                expression=exp.convert(bound.value),
            ),
            expression=exp.convert(100.0),
        )
    )


def _render_bounded_comparison(
    column,
    comparator: str,
    lower,
    upper=None,
    lower_inclusive: bool = True,
    upper_inclusive: bool = True,
):
    if comparator != "between":
        return _COMPARISON[comparator](this=column, expression=lower)
    if upper is None:
        raise DorisBackendError(
            "DORIS_RANK_BOUND_INVALID",
            "rank between requires an upper bound",
        )
    return exp.and_(
        (exp.GTE if lower_inclusive else exp.GT)(
            this=column.copy(),
            expression=lower,
        ),
        (exp.LTE if upper_inclusive else exp.LT)(
            this=column.copy(),
            expression=upper,
        ),
    )


def _render_composite_aggregate(
    plan: PhysicalCompositeAggregate,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    query = _render_plan(plan.input, catalog, cte_prefix)
    anchor_relation = _find_relation(plan.input)
    anchor_alias = _stable_alias(anchor_relation)
    keys = ("mktcode", "tgtcode")
    for group in plan.groups:
        aggregate_rows = _render_aggregate_group(group, catalog, cte_prefix).subquery(
            alias=group.alias
        )
        if group.group_by_security:
            join_predicate = exp.and_(
                *(
                    exp.EQ(
                        this=exp.column(key, table=anchor_alias, quoted=True),
                        expression=exp.column(key, table=group.alias, quoted=True),
                    )
                    for key in keys
                )
            )
            query = query.join(aggregate_rows, on=join_predicate, join_type="INNER")
        else:
            query = query.join(aggregate_rows, join_type="CROSS")
    for scalar in plan.scalars:
        scalar_rows = _render_named_scalar(scalar, catalog, cte_prefix).subquery(
            alias=scalar.alias
        )
        if scalar.group_by_security:
            join_predicate = exp.and_(
                *(
                    exp.EQ(
                        this=exp.column(key, table=anchor_alias, quoted=True),
                        expression=exp.column(key, table=scalar.alias, quoted=True),
                    )
                    for key in keys
                )
            )
            query = query.join(
                scalar_rows,
                on=join_predicate,
                join_type="INNER",
            )
        else:
            query = query.join(scalar_rows, join_type="CROSS")
    return query.where(_render_expr(plan.predicate, catalog, anchor_relation))


def _render_rank_expression(
    plan: PhysicalRankExpression,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    anchor_query = _render_plan(plan.input, catalog, cte_prefix)
    anchor_body, anchor_ctes = _detach_ctes(anchor_query)
    anchor_alias = f"{cte_prefix}rank_anchor_input"
    query = exp.select(
        *(exp.column(name, table=anchor_alias, quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
    ).from_(anchor_body.subquery(alias=anchor_alias))
    keys = ("mktcode", "tgtcode")
    for rank in plan.ranks:
        rank_rows = _render_named_rank(rank, catalog, cte_prefix).subquery(alias=rank.alias)
        join_predicate = exp.and_(
            *(
                exp.EQ(
                    this=exp.column(key, table=anchor_alias, quoted=True),
                    expression=exp.column(key, table=rank.alias, quoted=True),
                )
                for key in keys
            )
        )
        query = query.join(rank_rows, on=join_predicate, join_type="INNER")
    for scalar in plan.scalars:
        scalar_rows = _render_named_scalar(
            scalar,
            catalog,
            cte_prefix,
        ).subquery(alias=scalar.alias)
        if scalar.group_by_security:
            join_predicate = exp.and_(
                *(
                    exp.EQ(
                        this=exp.column(key, table=anchor_alias, quoted=True),
                        expression=exp.column(key, table=scalar.alias, quoted=True),
                    )
                    for key in keys
                )
            )
            query = query.join(
                scalar_rows,
                on=join_predicate,
                join_type="INNER",
            )
        else:
            query = query.join(scalar_rows, join_type="CROSS")
    query = query.where(_render_expr(plan.predicate, catalog))
    for cte in anchor_ctes:
        query = query.with_(cte.alias_or_name, as_=cte.this)
    return query


def _render_named_rank(
    rank: PhysicalNamedRank,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(rank.input, catalog, cte_prefix)
    relation = _find_relation(rank.input)
    stable_alias = _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    value = _render_expr(rank.expression, catalog, relation)
    if rank.aggregate_function is not None or rank.collapse_latest:
        metric = (
            _render_set_aggregate(
                rank.aggregate_function,
                value,
                exp.column("bizdate", table=stable_alias, quoted=True),
            )
            if rank.aggregate_function is not None
            else exp.func(
                "MAX_BY",
                value,
                exp.column("bizdate", table=stable_alias, quoted=True),
            )
        ).as_("metric_value", quoted=True)
        source.set(
            "expressions",
            [
                *(exp.column(key, table=stable_alias, quoted=True) for key in keys),
                metric,
            ],
        )
        source = source.group_by(
            *(exp.column(key, table=stable_alias, quoted=True) for key in keys)
        )
    else:
        source = source.select(value.as_("metric_value", quoted=True), append=True)
    metric_alias = f"{rank.alias}_metric"
    metrics = source.subquery(alias=metric_alias)
    order = _rank_order(
        exp.column("metric_value", table=metric_alias, quoted=True),
        rank.direction == "desc",
        metric_alias,
    )
    return exp.select(
        *(exp.column(key, table=metric_alias, quoted=True) for key in keys),
        exp.Window(this=_rank_function(), order=order).as_(rank.value_alias, quoted=True),
    ).from_(metrics)


def _render_stage_rank(
    plan: PhysicalStageRank,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    candidate_query = _render_plan(plan.input, catalog, f"{cte_prefix}stage_input_")
    candidate_body, candidate_ctes = _detach_ctes(candidate_query)
    candidate_alias = f"{cte_prefix}stage_{plan.stage_index}_candidates"
    candidate_raw_alias = f"{candidate_alias}_raw"
    candidate_distinct = exp.select(
        *(exp.column(key, table=candidate_raw_alias, quoted=True) for key in ("mktcode", "tgtcode")),
        exp.Max(
            this=exp.column("bizdate", table=candidate_raw_alias, quoted=True)
        ).as_("bizdate", quoted=True),
    ).from_(candidate_body.subquery(alias=candidate_raw_alias)).group_by(
        *(exp.column(key, table=candidate_raw_alias, quoted=True) for key in ("mktcode", "tgtcode"))
    )

    metric_query = _render_plan(
        plan.measure_input,
        catalog,
        f"{cte_prefix}stage_metric_",
    )
    metric_relation = _find_relation(plan.measure_input)
    stable_alias = _stable_alias(metric_relation)
    keys = ("mktcode", "tgtcode")
    metric_value = _render_expr(plan.measure, catalog, metric_relation)
    if plan.aggregate_function is not None or plan.collapse_latest:
        metric = (
            _render_set_aggregate(
                plan.aggregate_function,
                metric_value,
                exp.column("bizdate", table=stable_alias, quoted=True),
            )
            if plan.aggregate_function is not None
            else exp.func(
                "MAX_BY",
                metric_value,
                exp.column("bizdate", table=stable_alias, quoted=True),
            )
        ).as_("metric_value", quoted=True)
        metric_query.set(
            "expressions",
            [
                *(exp.column(key, table=stable_alias, quoted=True) for key in keys),
                metric,
            ],
        )
        metric_query = metric_query.group_by(
            *(exp.column(key, table=stable_alias, quoted=True) for key in keys)
        )
    else:
        metric_query = metric_query.select(
            metric_value.as_("metric_value", quoted=True),
            append=True,
        )
    metric_alias = f"{cte_prefix}stage_{plan.stage_index}_metric"
    candidate_table = candidate_distinct.subquery(alias=candidate_alias)
    metric_table = metric_query.subquery(alias=metric_alias)
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(key, table=candidate_alias, quoted=True),
                expression=exp.column(key, table=metric_alias, quoted=True),
            )
            for key in keys
        )
    )
    joined = exp.select(
        *(exp.column(name, table=candidate_alias, quoted=True) for name in (*keys, "bizdate")),
        exp.column("metric_value", table=metric_alias, quoted=True),
    ).from_(candidate_table).join(metric_table, on=join_predicate, join_type="INNER")
    joined_alias = f"{cte_prefix}stage_{plan.stage_index}_joined"
    joined_rows = joined.subquery(alias=joined_alias)
    order = _rank_order(
        exp.column("metric_value", table=joined_alias, quoted=True),
        plan.direction == "desc",
        joined_alias,
    )
    ranked = exp.select(
        *(exp.column(name, table=joined_alias, quoted=True) for name in (*keys, "bizdate")),
        exp.Window(this=_rank_function(), order=order).as_("stage_rank", quoted=True),
    ).from_(joined_rows)
    if plan.percentage:
        ranked = ranked.select(
            exp.Window(this=exp.Count(this=exp.Star())).as_(
                "stage_population", quoted=True
            ),
            append=True,
        )
    ranked_alias = f"{cte_prefix}stage_{plan.stage_index}_ranked"
    ranked_rows = ranked.subquery(alias=ranked_alias)
    def render_stage_bound(value):
        return (
            exp.Ceil(
                this=exp.Div(
                    this=exp.Mul(
                        this=exp.column(
                            "stage_population", table=ranked_alias, quoted=True
                        ),
                        expression=exp.convert(value.value),
                    ),
                    expression=exp.convert(100.0),
                )
            )
            if plan.percentage
            else exp.convert(value.value)
        )

    bound = render_stage_bound(plan.bound)
    result = exp.select(
        *(exp.column(name, table=ranked_alias, quoted=True) for name in (*keys, "bizdate"))
    ).from_(ranked_rows).where(
        _render_bounded_comparison(
            exp.column("stage_rank", table=ranked_alias, quoted=True),
            plan.comparator,
            bound,
            (
                render_stage_bound(plan.upper_bound)
                if plan.upper_bound is not None
                else None
            ),
            plan.lower_inclusive,
            plan.upper_inclusive,
        )
    )
    for cte in candidate_ctes:
        result = result.with_(cte.alias_or_name, as_=cte.this)
    return result


def _render_aggregate_group(
    group: PhysicalAggregateGroup,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(group.input, catalog, cte_prefix)
    relation = _find_relation(group.input)
    if group.industry_membership_resource_id is not None:
        return _render_industry_aggregate_group(
            group,
            source,
            relation,
            catalog,
        )
    stable_alias = _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    measures = [
        _render_set_aggregate(
            measure.function,
            _render_expr(measure.expression, catalog, relation),
            exp.column("bizdate", table=stable_alias, quoted=True),
        ).as_(measure.alias, quoted=True)
        for measure in group.measures
    ]
    group_keys = (
        [exp.column(key, table=stable_alias, quoted=True) for key in keys]
        if group.group_by_security
        else []
    )
    source.set("expressions", [*group_keys, *measures])
    return source.group_by(*group_keys) if group_keys else source


def _render_industry_aggregate_group(
    group: PhysicalAggregateGroup,
    source: exp.Select,
    relation,
    catalog: PhysicalCatalog,
) -> exp.Select:
    membership = catalog.resource(group.industry_membership_resource_id)
    source_alias = f"{group.alias}_source"
    member_alias = f"{group.alias}_member"
    values_alias = f"{group.alias}_industry_values"
    target_alias = f"{group.alias}_target"
    for measure in group.measures:
        source = source.select(
            _render_expr(measure.expression, catalog, relation).as_(
                measure.alias,
                quoted=True,
            ),
            append=True,
        )
    source_rows = source.subquery(alias=source_alias)
    member_table = exp.table_(
        membership.table,
        db=membership.database,
        quoted=True,
        alias=member_alias,
    )
    source_member_join = exp.and_(
        exp.EQ(
            this=exp.column("mktcode", table=source_alias, quoted=True),
            expression=exp.column("mktcode", table=member_alias, quoted=True),
        ),
        exp.EQ(
            this=exp.column("tgtcode", table=source_alias, quoted=True),
            expression=exp.column("tgtcode", table=member_alias, quoted=True),
        ),
    )
    policy = _industry_membership_policy_predicate(group, member_alias)
    industry_code = exp.column("industry_code", table=member_alias, quoted=True)
    aggregate_measures = [
        _render_set_aggregate(
            measure.function,
            exp.column(measure.alias, table=source_alias, quoted=True),
            exp.column("bizdate", table=source_alias, quoted=True),
        ).as_(measure.alias, quoted=True)
        for measure in group.measures
    ]
    values = (
        exp.select(
            industry_code.copy().as_("industry_code", quoted=True),
            *aggregate_measures,
        )
        .from_(source_rows)
        .join(member_table, on=source_member_join, join_type="INNER")
        .where(policy)
        .group_by(industry_code.copy())
    )

    target_table = exp.table_(
        membership.table,
        db=membership.database,
        quoted=True,
        alias=target_alias,
    )
    target_policy = _industry_membership_policy_predicate(group, target_alias)
    values_rows = values.subquery(alias=values_alias)
    return (
        exp.select(
            exp.column("mktcode", table=target_alias, quoted=True),
            exp.column("tgtcode", table=target_alias, quoted=True),
            *(
                exp.column(measure.alias, table=values_alias, quoted=True)
                for measure in group.measures
            ),
        )
        .from_(target_table)
        .join(
            values_rows,
            on=exp.EQ(
                this=exp.column("industry_code", table=target_alias, quoted=True),
                expression=exp.column(
                    "industry_code", table=values_alias, quoted=True
                ),
            ),
            join_type="INNER",
        )
        .where(target_policy)
    )


def _industry_membership_policy_predicate(group, alias: str):
    return exp.and_(
        exp.EQ(
            this=exp.column("snapshot_id", table=alias, quoted=True),
            expression=exp.convert(group.industry_snapshot_id),
        ),
        exp.EQ(
            this=exp.column("classification_system", table=alias, quoted=True),
            expression=exp.convert(group.industry_classification_system),
        ),
        exp.EQ(
            this=exp.column("industry_level", table=alias, quoted=True),
            expression=exp.convert(group.industry_level),
        ),
    )


def _render_named_scalar(scalar, catalog: PhysicalCatalog, cte_prefix: str = "") -> exp.Select:
    source = _render_plan(scalar.input, catalog, cte_prefix)
    relation = _find_relation(scalar.input)
    stable_alias = _stable_alias(relation)
    value = _render_expr(scalar.expression, catalog, relation)
    if scalar.function is not None:
        metric = exp.func(scalar.function.upper(), value).as_(
            scalar.value_alias, quoted=True
        )
        expressions = [metric]
        if scalar.group_by_security:
            expressions = [
                *(
                    exp.column(key, table=stable_alias, quoted=True)
                    for key in ("mktcode", "tgtcode")
                ),
                metric,
            ]
        source.set("expressions", expressions)
        if scalar.group_by_security:
            source = source.group_by(
                *(
                    exp.column(key, table=stable_alias, quoted=True)
                    for key in ("mktcode", "tgtcode")
                )
            )
        return source
    if scalar.collapse_latest:
        metric = exp.func(
            "MAX_BY",
            value,
            exp.column("bizdate", table=stable_alias, quoted=True),
        ).as_(scalar.value_alias, quoted=True)
        expressions = [metric]
        if scalar.group_by_security:
            expressions = [
                *(
                    exp.column(key, table=stable_alias, quoted=True)
                    for key in ("mktcode", "tgtcode")
                ),
                metric,
            ]
        source.set("expressions", expressions)
        if scalar.group_by_security:
            source = source.group_by(
                *(
                    exp.column(key, table=stable_alias, quoted=True)
                    for key in ("mktcode", "tgtcode")
                )
            )
        return source
    expressions = [value.as_(scalar.value_alias, quoted=True)]
    if scalar.group_by_security:
        expressions = [
            *(
                exp.column(key, table=stable_alias, quoted=True)
                for key in ("mktcode", "tgtcode")
            ),
            *expressions,
        ]
    source.set("expressions", expressions)
    return source


def _render_join(plan: PhysicalJoin, catalog: PhysicalCatalog) -> exp.Select:
    root, joins = _flatten_join(plan)
    root_resource = catalog.resource(root.resource_id)
    root_alias = root.resource_id
    projections = tuple(
        exp.column(name, table=root_alias, quoted=True)
        for name in ("mktcode", "tgtcode", "bizdate")
        if name in root_resource.stable_keys
    )
    query = exp.select(*projections).from_(
        exp.table_(
            root_resource.table,
            db=root_resource.database,
            quoted=True,
            alias=root_alias,
        )
    )
    if root.partition_predicate is not None:
        query = query.where(_render_expr(root.partition_predicate, catalog, plan))
    for right, join_type, keys in joins:
        resource = catalog.resource(right.resource_id)
        table = exp.table_(
            resource.table,
            db=resource.database,
            quoted=True,
            alias=right.resource_id,
        )
        predicate = exp.and_(
            *(
                exp.EQ(
                    this=exp.column(left.column, table=left.resource_id, quoted=True),
                    expression=exp.column(right_key.column, table=right_key.resource_id, quoted=True),
                )
                for left, right_key in keys
            )
        )
        query = query.join(table, on=predicate, join_type=join_type.upper())
        if right.partition_predicate is not None:
            query = query.where(_render_expr(right.partition_predicate, catalog, plan))
    return query


def _flatten_join(plan: PhysicalJoin):
    joins = []
    current = plan
    while isinstance(current, PhysicalJoin):
        if not isinstance(current.right, PhysicalTableScan):
            raise DorisBackendError(
                "DORIS_JOIN_SHAPE_UNSUPPORTED",
                "physical join must be a left-deep tree of table scans",
            )
        joins.append((current.right, current.join_type, current.keys))
        current = current.left
    if not isinstance(current, PhysicalTableScan):
        raise DorisBackendError(
            "DORIS_JOIN_SHAPE_UNSUPPORTED",
            "physical join root must be a table scan",
        )
    joins.reverse()
    return current, tuple(joins)


def _render_temporal(
    plan: PhysicalTemporal,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    event_projection = isinstance(plan.input, PhysicalEventProjection)
    relation = _find_relation(
        plan.input.input if event_projection else plan.input
    )
    if isinstance(relation, PhysicalScan):
        stable_resource_id = relation.anchor_resource_id or relation.resource_id
    elif isinstance(relation, PhysicalTableScan):
        stable_resource_id = relation.resource_id
    else:
        root, _ = _flatten_join(relation)
        stable_resource_id = root.resource_id
    stable_alias = "event_rows" if event_projection else _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    source_rows_name = f"{cte_prefix}source_rows"
    eligible_rows_name = f"{cte_prefix}eligible_rows"
    bucket_rows_name = f"{cte_prefix}bucket_rows"
    sequenced_rows_name = f"{cte_prefix}sequenced_rows"
    matched_rows_name = f"{cte_prefix}matched_rows"
    runs_name = f"{cte_prefix}runs"
    metrics_name = f"{cte_prefix}temporal_metrics"
    qualified_name = f"{cte_prefix}qualified"
    source = _render_plan(plan.input, catalog, cte_prefix)
    for scalar in plan.scalars:
        scalar_rows = _render_named_scalar(
            scalar, catalog, cte_prefix
        ).subquery(alias=scalar.alias)
        source = source.join(scalar_rows, join_type="CROSS")
    matched = exp.Case(
        ifs=[
            exp.If(
                this=_render_expr(plan.predicate, catalog, relation),
                true=exp.convert(1),
            )
        ],
        default=exp.convert(0),
    ).as_("matched", quoted=True)
    source = source.select(matched, append=True)

    needs_session_limit = plan.window.kind in {"recent_sessions", "session_slice", "latest_session"}
    if needs_session_limit:
        source = source.select(
            _row_number(
                stable_alias,
                keys,
                "bizdate",
                descending=True,
            ).as_("lookback_row", quoted=True),
            append=True,
        )
    elif plan.window.kind == "exact_date":
        source = source.where(
            exp.EQ(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                expression=exp.convert(plan.window.start),
            )
        )
    elif plan.window.kind == "calendar_range":
        source = source.where(
            exp.and_(
                exp.GTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=exp.convert(plan.window.start),
                ),
                exp.LTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=exp.convert(plan.window.end),
                ),
            )
        )
    elif plan.window.kind == "boundary_sessions":
        source = source.where(
            _render_expr(
                PhysicalSessionBoundaryRange(
                    stable_resource_id,
                    "bizdate",
                    plan.window.boundary_direction,
                    plan.window.boundary_kind,
                    plan.window.lookback_sessions or 1,
                    unit=plan.window.calendar_unit,
                    offset=plan.window.calendar_offset,
                    boundary_date=plan.window.boundary_date,
                    month=plan.window.anchor_month,
                    day=plan.window.anchor_day,
                ),
                catalog,
                relation,
            )
        )
    elif plan.window.kind == "recent_calendar":
        amount = plan.window.calendar_amount
        unit = plan.window.calendar_unit
        if amount is None or unit is None:
            raise DorisBackendError(
                "DORIS_TEMPORAL_WINDOW_INVALID",
                "recent calendar window is missing amount or unit",
            )
        lower, upper, _ = _dynamic_date_bounds(
            catalog,
            stable_resource_id,
            "recent",
            unit,
            amount,
            0,
            None,
            None,
        )
        source = source.where(
            exp.and_(
                exp.GTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=lower,
                ),
                exp.LTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=upper,
                ),
            )
        )
    elif plan.window.kind in {"dynamic_period", "anchor_calendar", "dynamic_weekday_range"}:
        amount = plan.window.calendar_amount or 1
        unit = plan.window.calendar_unit
        if unit is None:
            raise DorisBackendError(
                "DORIS_TEMPORAL_WINDOW_INVALID",
                "dynamic calendar window is missing its unit",
            )
        lower, upper, validity = _dynamic_date_bounds(
            catalog,
            stable_resource_id,
            (
                "period"
                if plan.window.kind == "dynamic_period"
                else "weekday_range"
                if plan.window.kind == "dynamic_weekday_range"
                else "anchor_calendar"
            ),
            unit,
            amount,
            plan.window.calendar_offset,
            plan.window.anchor_month,
            plan.window.anchor_day,
            weekday_start=plan.window.weekday_start,
            weekday_end=plan.window.weekday_end,
        )
        bounds = exp.and_(
            exp.GTE(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                expression=lower,
            ),
            exp.LTE(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                expression=upper,
            ),
        )
        source = source.where(exp.and_(bounds, validity) if validity is not None else bounds)

    ctes = [(source_rows_name, source)]
    relation_name = source_rows_name
    if needs_session_limit:
        lookback = plan.window.lookback_sessions or 1
        offset = plan.window.session_offset
        session_bounds = exp.LTE(
                this=exp.column("lookback_row", table=source_rows_name, quoted=True),
                expression=exp.convert(offset + lookback),
        )
        if offset:
            session_bounds = exp.and_(
                exp.GT(
                    this=exp.column("lookback_row", table=source_rows_name, quoted=True),
                    expression=exp.convert(offset),
                ),
                session_bounds,
            )
        eligible = exp.select(exp.Star()).from_(exp.table_(source_rows_name, quoted=True)).where(session_bounds)
        ctes.append((eligible_rows_name, eligible))
        relation_name = eligible_rows_name

    calendar_bucket = plan.unit in {"周", "月", "季度", "年"}
    if calendar_bucket:
        bucket_key = _calendar_bucket_key(relation_name, plan.unit)
        bucket_ordinal = _calendar_bucket_ordinal(bucket_key, plan.unit)
        bucket_rows = exp.select(
            *(exp.column(name, table=relation_name, quoted=True) for name in keys),
            bucket_key.as_("bucket_key", quoted=True),
            exp.Max(this=exp.column("matched", table=relation_name, quoted=True)).as_("matched", quoted=True),
            bucket_ordinal.as_("bucket_ordinal", quoted=True),
        ).from_(exp.table_(relation_name, quoted=True)).group_by(
            *(exp.column(name, table=relation_name, quoted=True) for name in keys),
            bucket_key,
            bucket_ordinal,
        )
        ctes.append((bucket_rows_name, bucket_rows))
        relation_name = bucket_rows_name

    if plan.every or plan.mode == "EXIST":
        metrics = _render_exist_metrics(
            relation_name,
            keys,
            gap_aware=calendar_bucket and plan.every,
        )
    else:
        if calendar_bucket:
            matched_projection = (*keys, "bucket_key", "bucket_ordinal")
            order_column = "bucket_key"
            sequence_column = "bucket_ordinal"
        else:
            matched_projection = (*keys, "bizdate", "all_seq")
            order_column = "bizdate"
            sequence_column = "all_seq"
        matched_rows = exp.select(
            *(exp.column(name, table=relation_name, quoted=True) for name in matched_projection)
        ).from_(exp.table_(relation_name, quoted=True)).where(
            exp.EQ(
                this=exp.column("matched", table=relation_name, quoted=True),
                expression=exp.convert(1),
            )
        )
        matched_rows = matched_rows.select(
            _row_number(relation_name, keys, order_column).as_("matched_seq", quoted=True),
            append=True,
        )
        ctes.append((matched_rows_name, matched_rows))

        island = exp.Sub(
            this=exp.column(sequence_column, table=matched_rows_name, quoted=True),
            expression=exp.column("matched_seq", table=matched_rows_name, quoted=True),
        )
        runs = exp.select(
            *(exp.column(name, table=matched_rows_name, quoted=True) for name in keys),
            island.as_("run_group", quoted=True),
            exp.Count(this=exp.Star()).as_("run_length", quoted=True),
        ).from_(exp.table_(matched_rows_name, quoted=True)).group_by(
            *(exp.column(name, table=matched_rows_name, quoted=True) for name in keys),
            island,
        )
        ctes.append((runs_name, runs))
        metrics = exp.select(
            *(exp.column(name, table=runs_name, quoted=True) for name in keys),
            exp.Max(this=exp.column("run_length", table=runs_name, quoted=True)).as_("metric_value", quoted=True),
            exp.Count(this=exp.Star()).as_("total_buckets", quoted=True),
        ).from_(exp.table_(runs_name, quoted=True)).group_by(
            *(exp.column(name, table=runs_name, quoted=True) for name in keys)
        )

    if plan.mode == "CONS" and not plan.every and not calendar_bucket:
        sequence_relation = relation_name
        sequence = exp.select(
            *(exp.column(name, table=sequence_relation, quoted=True) for name in (*keys, "bizdate", "matched")),
            _row_number(sequence_relation, keys, "bizdate").as_("all_seq", quoted=True),
        ).from_(exp.table_(sequence_relation, quoted=True))
        insert_at = 2 if needs_session_limit else 1
        ctes.insert(insert_at, (sequenced_rows_name, sequence))
        for index, (name, query) in enumerate(ctes):
            if name == matched_rows_name:
                ctes[index] = (name, _replace_table(query, relation_name, sequenced_rows_name))
        relation_name = sequenced_rows_name

    ctes.append((metrics_name, metrics))
    qualified_predicate = _temporal_metric_predicate(plan, metrics_name)
    qualified = exp.select(
        *(exp.column(name, table=metrics_name, quoted=True) for name in keys)
    ).from_(exp.table_(metrics_name, quoted=True)).where(qualified_predicate)
    ctes.append((qualified_name, qualified))

    anchor_resource = catalog.resource(stable_resource_id)
    anchor = exp.table_(
        anchor_resource.table,
        db=anchor_resource.database,
        quoted=True,
        alias="anchor_out",
    )
    qualified_alias = f"{cte_prefix}qualified_result"
    qualified_table = exp.table_(qualified_name, quoted=True, alias=qualified_alias)
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(name, table="anchor_out", quoted=True),
                expression=exp.column(name, table=qualified_alias, quoted=True),
            )
            for name in keys
        )
    )
    final = exp.select(
        *(exp.column(name, table="anchor_out", quoted=True) for name in (*keys, "bizdate"))
    ).from_(anchor).join(qualified_table, on=join_predicate, join_type="INNER")
    latest = exp.select(
        exp.Max(this=exp.column("bizdate", table="latest_anchor", quoted=True))
    ).from_(
        exp.table_(
            anchor_resource.table,
            db=anchor_resource.database,
            quoted=True,
            alias="latest_anchor",
        )
    )
    final = final.where(
        exp.EQ(
            this=exp.column("bizdate", table="anchor_out", quoted=True),
            expression=exp.Subquery(this=latest),
        )
    )
    for name, query in ctes:
        final = final.with_(name, as_=query)
    return final


def _render_temporal_aggregate(
    plan,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    is_rank = isinstance(plan, PhysicalTemporalRank)
    function = plan.aggregate_function if is_rank else plan.function
    value_comparator = plan.rank_comparator if is_rank else plan.value_comparator
    value_bound = plan.rank_bound if is_rank else plan.value_bound
    scan = _find_scan(plan.input)
    stable_alias = "anchor" if scan.anchor_resource_id else "q"
    keys = ("mktcode", "tgtcode")
    names = {
        name: f"{cte_prefix}{name}"
        for name in (
            "aggregate_source",
            "aggregate_eligible",
            "aggregate_daily",
            "aggregate_lag",
            "aggregate_metric",
            "aggregate_ranked",
            "aggregate_matched",
            "aggregate_bucketed",
            "aggregate_sequenced",
            "aggregate_hits",
            "aggregate_runs",
            "aggregate_temporal_metrics",
            "aggregate_qualified",
        )
    }
    source = _render_plan(plan.input, catalog, cte_prefix).select(
        _render_expr(plan.measure, catalog, scan).as_("measure_value", quoted=True),
        append=True,
    )
    needs_session_limit = plan.window.kind in {
        "recent_sessions",
        "session_slice",
        "latest_session",
    }
    if needs_session_limit:
        source = source.select(
            _row_number(stable_alias, keys, "bizdate", descending=True).as_(
                "lookback_row", quoted=True
            ),
            append=True,
        )
    elif plan.window.kind == "exact_date":
        source = source.where(
            exp.EQ(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                expression=exp.convert(plan.window.start),
            )
        )
    elif plan.window.kind == "calendar_range":
        source = source.where(
            exp.and_(
                exp.GTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=exp.convert(plan.window.start),
                ),
                exp.LTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=exp.convert(plan.window.end),
                ),
            )
        )
    elif plan.window.kind == "boundary_sessions":
        source = source.where(
            _render_expr(
                PhysicalSessionBoundaryRange(
                    scan.anchor_resource_id or scan.resource_id,
                    "bizdate",
                    plan.window.boundary_direction,
                    plan.window.boundary_kind,
                    plan.window.lookback_sessions or 1,
                    unit=plan.window.calendar_unit,
                    offset=plan.window.calendar_offset,
                    boundary_date=plan.window.boundary_date,
                    month=plan.window.anchor_month,
                    day=plan.window.anchor_day,
                ),
                catalog,
                scan,
            )
        )
    elif plan.window.kind == "recent_calendar":
        lower, upper, _ = _dynamic_date_bounds(
            catalog,
            scan.anchor_resource_id or scan.resource_id,
            "recent",
            plan.window.calendar_unit,
            plan.window.calendar_amount or 1,
            0,
            None,
            None,
        )
        source = source.where(
            exp.and_(
                exp.GTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=lower,
                ),
                exp.LTE(
                    this=exp.column("bizdate", table=stable_alias, quoted=True),
                    expression=upper,
                ),
            )
        )
    elif plan.window.kind in {"dynamic_period", "anchor_calendar", "dynamic_weekday_range"}:
        lower, upper, validity = _dynamic_date_bounds(
            catalog,
            scan.anchor_resource_id or scan.resource_id,
            (
                "period"
                if plan.window.kind == "dynamic_period"
                else "weekday_range"
                if plan.window.kind == "dynamic_weekday_range"
                else "anchor_calendar"
            ),
            plan.window.calendar_unit,
            plan.window.calendar_amount or 1,
            plan.window.calendar_offset,
            plan.window.anchor_month,
            plan.window.anchor_day,
            weekday_start=plan.window.weekday_start,
            weekday_end=plan.window.weekday_end,
        )
        bounds = exp.and_(
            exp.GTE(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                expression=lower,
            ),
            exp.LTE(
                this=exp.column("bizdate", table=stable_alias, quoted=True),
                expression=upper,
            ),
        )
        source = source.where(exp.and_(bounds, validity) if validity is not None else bounds)

    ctes = [(names["aggregate_source"], source)]
    relation_name = names["aggregate_source"]
    if needs_session_limit:
        lookback = plan.window.lookback_sessions or 1
        offset = plan.window.session_offset
        bounds = exp.LTE(
            this=exp.column("lookback_row", table=relation_name, quoted=True),
            expression=exp.convert(offset + lookback),
        )
        if offset:
            bounds = exp.and_(
                exp.GT(
                    this=exp.column("lookback_row", table=relation_name, quoted=True),
                    expression=exp.convert(offset),
                ),
                bounds,
            )
        eligible = exp.select(exp.Star()).from_(
            exp.table_(relation_name, quoted=True)
        ).where(bounds)
        ctes.append((names["aggregate_eligible"], eligible))
        relation_name = names["aggregate_eligible"]

    calendar_bucket = plan.unit in {"周", "月", "季度", "年"}
    aggregate_before_rank = calendar_bucket and (not is_rank or function is not None)
    value = exp.column("measure_value", table=relation_name, quoted=True)
    date = exp.column("bizdate", table=relation_name, quoted=True)
    if aggregate_before_rank:
        bucket_key = _calendar_bucket_key(relation_name, plan.unit)
        bucket_ordinal = _calendar_bucket_ordinal(bucket_key, plan.unit)
        metric = _render_set_aggregate(function, value, date)
        metric_rows = exp.select(
            *(exp.column(name, table=relation_name, quoted=True) for name in keys),
            bucket_key.as_("bucket_key", quoted=True),
            bucket_ordinal.as_("bucket_ordinal", quoted=True),
            metric.as_("metric_value", quoted=True),
        ).from_(exp.table_(relation_name, quoted=True)).group_by(
            *(exp.column(name, table=relation_name, quoted=True) for name in keys),
            bucket_key,
            bucket_ordinal,
        )
        ctes.append((names["aggregate_metric"], metric_rows))
        metric_name = names["aggregate_metric"]
        order_column = "bucket_key"
        sequence_column = "bucket_ordinal"
        projection = (*keys, "bucket_key", "bucket_ordinal", "metric_value")
    else:
        daily_function = function if function in {"sum", "avg", "max", "min"} else "max"
        daily_rows = exp.select(
            *(exp.column(name, table=relation_name, quoted=True) for name in keys),
            date.copy(),
            _render_set_aggregate(daily_function, value, date).as_(
                "daily_value", quoted=True
            ),
        ).from_(exp.table_(relation_name, quoted=True)).group_by(
            *(exp.column(name, table=relation_name, quoted=True) for name in (*keys, "bizdate"))
        )
        ctes.append((names["aggregate_daily"], daily_rows))
        daily_name = names["aggregate_daily"]
        current = exp.column("daily_value", table=daily_name, quoted=True)
        if function in {"growth_rise", "growth_fall"}:
            previous = exp.Window(
                this=exp.Lag(this=current.copy()),
                partition_by=[
                    exp.column(name, table=daily_name, quoted=True) for name in keys
                ],
                order=exp.Order(
                    expressions=[
                        exp.Ordered(
                            this=exp.column("bizdate", table=daily_name, quoted=True),
                            desc=False,
                        )
                    ]
                ),
            )
            lag_rows = exp.select(
                *(exp.column(name, table=daily_name, quoted=True) for name in (*keys, "bizdate", "daily_value")),
                previous.as_("previous_value", quoted=True),
            ).from_(exp.table_(daily_name, quoted=True))
            ctes.append((names["aggregate_lag"], lag_rows))
            daily_name = names["aggregate_lag"]
            current = exp.column("daily_value", table=daily_name, quoted=True)
            previous_value = exp.column("previous_value", table=daily_name, quoted=True)
            delta = (
                exp.Sub(this=current.copy(), expression=previous_value.copy())
                if function == "growth_rise"
                else exp.Sub(this=previous_value.copy(), expression=current.copy())
            )
            metric = exp.Div(
                this=exp.Mul(
                    this=exp.Paren(this=delta),
                    expression=exp.convert(100),
                ),
                expression=exp.Nullif(
                    this=exp.Abs(this=previous_value),
                    expression=exp.convert(0),
                ),
            )
        else:
            metric = current
        metric_rows = exp.select(
            *(exp.column(name, table=daily_name, quoted=True) for name in (*keys, "bizdate")),
            metric.as_("metric_value", quoted=True),
        ).from_(exp.table_(daily_name, quoted=True))
        ctes.append((names["aggregate_metric"], metric_rows))
        metric_name = names["aggregate_metric"]
        order_column = "bizdate"
        sequence_column = "all_seq"
        projection = (*keys, "bizdate", "metric_value")

    if is_rank:
        rank_partition = (
            [exp.column("bucket_key", table=metric_name, quoted=True)]
            if aggregate_before_rank
            else [exp.column("bizdate", table=metric_name, quoted=True)]
        )
        rank_order = _rank_order(
            exp.column("metric_value", table=metric_name, quoted=True),
            plan.direction == "desc",
            metric_name,
        )
        ranked = exp.select(
            *(exp.column(name, table=metric_name, quoted=True) for name in projection),
            exp.Window(
                this=_rank_function(),
                partition_by=rank_partition,
                order=rank_order,
            ).as_("rank_value", quoted=True),
        ).from_(exp.table_(metric_name, quoted=True))
        if plan.rank_percentage:
            ranked = ranked.select(
                exp.Window(
                    this=exp.Count(this=exp.Star()),
                    partition_by=[item.copy() for item in rank_partition],
                ).as_("rank_population", quoted=True),
                append=True,
            )
            projection = (*projection, "rank_population")
        projection = (*projection, "rank_value")
        ctes.append((names["aggregate_ranked"], ranked))
        metric_name = names["aggregate_ranked"]
        def render_temporal_rank_bound(bound):
            return (
                exp.Ceil(
                    this=exp.Div(
                        this=exp.Mul(
                            this=exp.column(
                                "rank_population", table=metric_name, quoted=True
                            ),
                            expression=exp.convert(bound.value),
                        ),
                        expression=exp.convert(100.0),
                    )
                )
                if plan.rank_percentage
                else exp.convert(bound.value)
            )

        rank_bound = render_temporal_rank_bound(value_bound)
        predicate_left = exp.column("rank_value", table=metric_name, quoted=True)
        predicate_right = rank_bound
    else:
        predicate_left = exp.column("metric_value", table=metric_name, quoted=True)
        predicate_right = exp.convert(value_bound.value)
    if is_rank and value_comparator == "between":
        if plan.rank_upper_bound is None:
            raise DorisBackendError(
                "DORIS_RANK_BOUND_INVALID",
                "temporal rank between requires an upper bound",
            )
        lower_operator = exp.GTE if plan.rank_lower_inclusive else exp.GT
        upper_operator = exp.LTE if plan.rank_upper_inclusive else exp.LT
        value_predicate = exp.and_(
            lower_operator(
                this=predicate_left.copy(),
                expression=predicate_right,
            ),
            upper_operator(
                this=predicate_left.copy(),
                expression=render_temporal_rank_bound(plan.rank_upper_bound),
            ),
        )
    else:
        value_predicate = _COMPARISON[value_comparator](
            this=predicate_left,
            expression=predicate_right,
        )
    matched = exp.select(
        *(exp.column(name, table=metric_name, quoted=True) for name in projection),
        exp.Case(
            ifs=[exp.If(this=value_predicate, true=exp.convert(1))],
            default=exp.convert(0),
        ).as_("matched", quoted=True),
    ).from_(exp.table_(metric_name, quoted=True))
    ctes.append((names["aggregate_matched"], matched))
    matched_name = names["aggregate_matched"]

    if is_rank and calendar_bucket and not aggregate_before_rank:
        bucket_key = _calendar_bucket_key(matched_name, plan.unit)
        bucket_ordinal = _calendar_bucket_ordinal(bucket_key, plan.unit)
        bucketed = exp.select(
            *(exp.column(name, table=matched_name, quoted=True) for name in keys),
            bucket_key.as_("bucket_key", quoted=True),
            bucket_ordinal.as_("bucket_ordinal", quoted=True),
            exp.Max(this=exp.column("matched", table=matched_name, quoted=True)).as_(
                "matched", quoted=True
            ),
        ).from_(exp.table_(matched_name, quoted=True)).group_by(
            *(exp.column(name, table=matched_name, quoted=True) for name in keys),
            bucket_key,
            bucket_ordinal,
        )
        ctes.append((names["aggregate_bucketed"], bucketed))
        matched_name = names["aggregate_bucketed"]
        order_column = "bucket_key"
        sequence_column = "bucket_ordinal"
        projection = (*keys, "bucket_key", "bucket_ordinal")

    if plan.every or plan.mode == "EXIST":
        metrics = _render_exist_metrics(
            matched_name,
            keys,
            gap_aware=calendar_bucket and plan.every,
        )
    else:
        sequenced = exp.select(
            *(exp.column(name, table=matched_name, quoted=True) for name in projection),
            exp.column("matched", table=matched_name, quoted=True),
            _row_number(matched_name, keys, order_column).as_("all_seq", quoted=True),
        ).from_(exp.table_(matched_name, quoted=True))
        ctes.append((names["aggregate_sequenced"], sequenced))
        sequenced_name = names["aggregate_sequenced"]
        hit_projection = (
            (*keys, "bucket_key", "bucket_ordinal", "all_seq")
            if calendar_bucket
            else (*keys, "bizdate", "all_seq")
        )
        hits = exp.select(
            *(exp.column(name, table=sequenced_name, quoted=True) for name in hit_projection),
            _row_number(sequenced_name, keys, order_column).as_("matched_seq", quoted=True),
        ).from_(exp.table_(sequenced_name, quoted=True)).where(
            exp.EQ(
                this=exp.column("matched", table=sequenced_name, quoted=True),
                expression=exp.convert(1),
            )
        )
        ctes.append((names["aggregate_hits"], hits))
        hits_name = names["aggregate_hits"]
        base_sequence = exp.column(sequence_column, table=hits_name, quoted=True)
        island = exp.Sub(
            this=base_sequence,
            expression=exp.column("matched_seq", table=hits_name, quoted=True),
        )
        runs = exp.select(
            *(exp.column(name, table=hits_name, quoted=True) for name in keys),
            island.as_("run_group", quoted=True),
            exp.Count(this=exp.Star()).as_("run_length", quoted=True),
        ).from_(exp.table_(hits_name, quoted=True)).group_by(
            *(exp.column(name, table=hits_name, quoted=True) for name in keys),
            island,
        )
        ctes.append((names["aggregate_runs"], runs))
        runs_name = names["aggregate_runs"]
        metrics = exp.select(
            *(exp.column(name, table=runs_name, quoted=True) for name in keys),
            exp.Max(this=exp.column("run_length", table=runs_name, quoted=True)).as_(
                "metric_value", quoted=True
            ),
            exp.Count(this=exp.Star()).as_("total_buckets", quoted=True),
        ).from_(exp.table_(runs_name, quoted=True)).group_by(
            *(exp.column(name, table=runs_name, quoted=True) for name in keys)
        )

    metrics_name = names["aggregate_temporal_metrics"]
    ctes.append((metrics_name, metrics))
    qualified_name = names["aggregate_qualified"]
    qualified = exp.select(
        *(exp.column(name, table=metrics_name, quoted=True) for name in keys)
    ).from_(exp.table_(metrics_name, quoted=True)).where(
        _temporal_metric_predicate(plan, metrics_name)
    )
    ctes.append((qualified_name, qualified))

    anchor_resource = catalog.resource(plan.anchor_resource_id)
    anchor = exp.table_(
        anchor_resource.table,
        db=anchor_resource.database,
        quoted=True,
        alias="anchor_out",
    )
    qualified_alias = f"{cte_prefix}aggregate_qualified_result"
    qualified_table = exp.table_(qualified_name, quoted=True, alias=qualified_alias)
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(name, table="anchor_out", quoted=True),
                expression=exp.column(name, table=qualified_alias, quoted=True),
            )
            for name in keys
        )
    )
    final = exp.select(
        *(exp.column(name, table="anchor_out", quoted=True) for name in (*keys, "bizdate"))
    ).from_(anchor).join(qualified_table, on=join_predicate, join_type="INNER")
    latest = exp.select(
        exp.Max(this=exp.column("bizdate", table="latest_anchor", quoted=True))
    ).from_(
        exp.table_(
            anchor_resource.table,
            db=anchor_resource.database,
            quoted=True,
            alias="latest_anchor",
        )
    )
    final = final.where(
        exp.EQ(
            this=exp.column("bizdate", table="anchor_out", quoted=True),
            expression=exp.Subquery(this=latest),
        )
    )
    for name, query in ctes:
        final = final.with_(name, as_=query)
    return final


def _render_set_operation(
    plan: PhysicalSetOperation,
    catalog: PhysicalCatalog,
    cte_prefix: str,
) -> exp.Select:
    left = _render_plan(plan.left, catalog, f"{cte_prefix}left_")
    right = _render_plan(plan.right, catalog, f"{cte_prefix}right_")
    left_body, left_ctes = _detach_ctes(left)
    right_body, right_ctes = _detach_ctes(right)
    if plan.operation == "intersect":
        combined = exp.Intersect(this=left_body, expression=right_body, distinct=True)
    else:
        combined = exp.Union(this=left_body, expression=right_body, distinct=True)
    alias = f"{cte_prefix}set_rows"
    result = exp.select(
        *(exp.column(name, table=alias, quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
    ).from_(combined.subquery(alias=alias))
    for cte in (*left_ctes, *right_ctes):
        result = result.with_(cte.alias_or_name, as_=cte.this)
    return result


def _render_candidate_set_operation(
    plan: PhysicalCandidateSetOperation,
    catalog: PhysicalCatalog,
    cte_prefix: str,
) -> exp.Select:
    keys = ("mktcode", "tgtcode")
    left = _render_plan(plan.left, catalog, f"{cte_prefix}candidate_left_")
    right = _render_plan(plan.right, catalog, f"{cte_prefix}candidate_right_")
    left_body, left_ctes = _detach_ctes(left)
    right_body, right_ctes = _detach_ctes(right)
    left_alias = f"{cte_prefix}candidate_left_rows"
    right_alias = f"{cte_prefix}candidate_right_rows"
    left_keys = (
        exp.select(
            *(exp.column(key, table=left_alias, quoted=True) for key in keys)
        )
        .distinct()
        .from_(left_body.subquery(alias=left_alias))
    )
    right_keys = (
        exp.select(
            *(exp.column(key, table=right_alias, quoted=True) for key in keys)
        )
        .distinct()
        .from_(right_body.subquery(alias=right_alias))
    )
    if plan.operation == "intersect":
        combined = exp.Intersect(this=left_keys, expression=right_keys, distinct=True)
    elif plan.operation == "union":
        combined = exp.Union(this=left_keys, expression=right_keys, distinct=True)
    else:
        combined = exp.Except(this=left_keys, expression=right_keys, distinct=True)

    candidate_alias = f"{cte_prefix}candidate_keys"
    anchor_alias = f"{cte_prefix}candidate_anchor"
    latest_alias = f"{cte_prefix}candidate_latest"
    anchor = catalog.resource(plan.anchor_resource_id)
    anchor_table = exp.table_(
        anchor.table,
        db=anchor.database,
        quoted=True,
        alias=anchor_alias,
    )
    latest_table = exp.table_(
        anchor.table,
        db=anchor.database,
        quoted=True,
        alias=latest_alias,
    )
    latest = exp.select(
        exp.Max(
            this=exp.column(anchor.partition_key, table=latest_alias, quoted=True)
        )
    ).from_(latest_table)
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(key, table=anchor_alias, quoted=True),
                expression=exp.column(key, table=candidate_alias, quoted=True),
            )
            for key in keys
        )
    )
    result = (
        exp.select(
            *(exp.column(key, table=anchor_alias, quoted=True) for key in (*keys, "bizdate"))
        )
        .from_(anchor_table)
        .join(combined.subquery(alias=candidate_alias), on=join_predicate, join_type="INNER")
        .where(
            exp.EQ(
                this=exp.column(anchor.partition_key, table=anchor_alias, quoted=True),
                expression=exp.Subquery(this=latest),
            )
        )
    )
    for cte in (*left_ctes, *right_ctes):
        result = result.with_(cte.alias_or_name, as_=cte.this)
    return result


def _detach_ctes(query: exp.Select):
    result = query.copy()
    with_clause = result.args.get("with_")
    ctes = tuple(with_clause.expressions) if with_clause is not None else ()
    result.set("with_", None)
    return result, ctes


def _render_exist_metrics(
    relation_name: str,
    keys,
    *,
    gap_aware: bool = False,
) -> exp.Select:
    if gap_aware:
        total_buckets = exp.Add(
            this=exp.Sub(
                this=exp.Max(this=exp.column("bucket_ordinal", table=relation_name, quoted=True)),
                expression=exp.Min(this=exp.column("bucket_ordinal", table=relation_name, quoted=True)),
            ),
            expression=exp.convert(1),
        )
    else:
        total_buckets = exp.Count(this=exp.Star())
    return exp.select(
        *(exp.column(name, table=relation_name, quoted=True) for name in keys),
        exp.Sum(this=exp.column("matched", table=relation_name, quoted=True)).as_("metric_value", quoted=True),
        total_buckets.as_("total_buckets", quoted=True),
    ).from_(exp.table_(relation_name, quoted=True)).group_by(
        *(exp.column(name, table=relation_name, quoted=True) for name in keys)
    )


def _calendar_bucket_key(relation_name: str, unit: str):
    granularity = {
        "周": "WEEK",
        "月": "MONTH",
        "季度": "QUARTER",
        "年": "YEAR",
    }[unit]
    return exp.DateTrunc(
        this=exp.column("bizdate", table=relation_name, quoted=True),
        unit=exp.Literal.string(granularity),
    )


def _calendar_bucket_ordinal(bucket_key, unit: str):
    if unit == "年":
        return exp.func("YEAR", bucket_key.copy())
    if unit == "月":
        return exp.Add(
            this=exp.Mul(
                this=exp.func("YEAR", bucket_key.copy()),
                expression=exp.convert(12),
            ),
            expression=exp.func("MONTH", bucket_key.copy()),
        )
    if unit == "季度":
        return exp.Add(
            this=exp.Mul(
                this=exp.func("YEAR", bucket_key.copy()),
                expression=exp.convert(4),
            ),
            expression=exp.func("QUARTER", bucket_key.copy()),
        )
    return exp.Floor(
        this=exp.Div(
            this=exp.func("UNIX_TIMESTAMP", bucket_key.copy()),
            expression=exp.convert(604800),
        )
    )


def _latest_calendar_anchor(catalog: PhysicalCatalog, scan: PhysicalScan) -> exp.Subquery:
    resource = catalog.resource(scan.anchor_resource_id or scan.resource_id)
    query = exp.select(
        exp.Max(this=exp.column("bizdate", table="calendar_anchor", quoted=True))
    ).from_(
        exp.table_(
            resource.table,
            db=resource.database,
            quoted=True,
            alias="calendar_anchor",
        )
    )
    return exp.Subquery(this=query)


def _latest_resource_anchor(catalog: PhysicalCatalog, resource_id: str) -> exp.Subquery:
    resource = catalog.resource(resource_id)
    if resource.partition_key is None:
        raise DorisBackendError(
            "DORIS_DATE_ANCHOR_UNAVAILABLE",
            f"resource {resource_id} has no partition key",
        )
    query = exp.select(
        exp.Max(this=exp.column(resource.partition_key, table="calendar_anchor", quoted=True))
    ).from_(
        exp.table_(
            resource.table,
            db=resource.database,
            quoted=True,
            alias="calendar_anchor",
        )
    )
    return exp.Subquery(this=query)


def _date_shift(value, amount: int, unit: str):
    if amount == 0:
        return value
    operator = exp.DateAdd if amount > 0 else exp.DateSub
    return operator(
        this=value,
        expression=exp.Literal.string(str(abs(amount))),
        unit=exp.Var(this=unit.upper()),
    )


def _date_trunc(value, unit: str):
    return exp.DateTrunc(this=value, unit=exp.Literal.string(unit.upper()))


def _dynamic_date_bounds(
    catalog: PhysicalCatalog,
    resource_id: str,
    range_kind: str,
    unit: str,
    amount: int,
    offset: int,
    month: Optional[int],
    day: Optional[int],
    end_month: Optional[int] = None,
    anchor_resource_id: Optional[str] = None,
    weekday_start: Optional[int] = None,
    weekday_end: Optional[int] = None,
):
    anchor = _latest_resource_anchor(catalog, anchor_resource_id or resource_id)
    validity = None
    if range_kind == "period":
        current_start = _date_trunc(anchor.copy(), unit)
        lower = _date_shift(current_start.copy(), offset, unit)
        upper = (
            anchor.copy()
            if offset == 0
            else _date_shift(
                _date_shift(current_start.copy(), offset + 1, unit),
                -1,
                "day",
            )
        )
        return lower, upper, validity
    if range_kind == "weekday_range":
        if weekday_start is None or weekday_end is None or weekday_start > weekday_end:
            raise DorisBackendError(
                "DORIS_DATE_RANGE_UNSUPPORTED",
                "weekday range requires ordered weekday boundaries",
            )
        week_start = _date_shift(_date_trunc(anchor.copy(), "week"), offset, "week")
        lower = _date_shift(week_start.copy(), weekday_start - 1, "day")
        upper = _date_shift(week_start.copy(), weekday_end - 1, "day")
        return lower, upper, validity
    if range_kind == "recent":
        if unit == "week":
            lower = _date_shift(anchor.copy(), -(amount * 7 - 1), "day")
        elif unit == "month":
            lower = _date_shift(_date_shift(anchor.copy(), -amount, "month"), 1, "day")
        elif unit == "year":
            lower = _date_trunc(
                _date_shift(anchor.copy(), -(amount - 1), "year"),
                "year",
            )
        else:
            raise DorisBackendError(
                "DORIS_DATE_RANGE_UNSUPPORTED",
                f"unsupported recent calendar unit {unit}",
            )
        return lower, anchor.copy(), validity
    if range_kind == "anchor_calendar":
        base = (
            _date_trunc(anchor.copy(), "month")
            if month is None
            else _date_shift(
                _date_trunc(anchor.copy(), "year"),
                month - 1 + offset,
                "month",
            )
        )
        if day is not None:
            lower = _date_shift(base.copy(), day - 1, "day")
            upper = lower.copy()
            expected_month = (
                exp.convert(month)
                if month is not None
                else exp.func("MONTH", anchor.copy())
            )
            validity = exp.EQ(
                this=exp.func("MONTH", lower.copy()),
                expression=expected_month,
            )
        else:
            lower = base.copy()
            upper = _date_shift(_date_shift(base.copy(), 1, "month"), -1, "day")
        return lower, upper, validity
    if range_kind == "year_month_range":
        if month is None or end_month is None:
            raise DorisBackendError(
                "DORIS_DATE_RANGE_UNSUPPORTED",
                "year month range requires both month boundaries",
            )
        year_start = _date_trunc(anchor.copy(), "year")
        lower = _date_shift(year_start.copy(), month - 1, "month")
        upper = _date_shift(
            _date_shift(year_start.copy(), end_month, "month"), -1, "day"
        )
        return lower, upper, validity
    raise DorisBackendError(
        "DORIS_DATE_RANGE_UNSUPPORTED",
        f"unsupported dynamic date range kind {range_kind}",
    )


def _row_number(table: str, keys, order_column: str, descending: bool = False) -> exp.Window:
    return exp.Window(
        this=exp.RowNumber(),
        partition_by=[exp.column(name, table=table, quoted=True) for name in keys],
        order=exp.Order(
            expressions=[
                exp.Ordered(
                    this=exp.column(order_column, table=table, quoted=True),
                    desc=descending,
                )
            ]
        ),
    )


def _rank_function():
    policy = current_semantic_policy()
    method = policy.ranking.method if policy else "row_number"
    if method == "row_number":
        return exp.RowNumber()
    if method == "rank":
        return exp.Rank()
    if method == "dense_rank":
        return exp.DenseRank()
    raise DorisBackendError("DORIS_RANK_POLICY_UNSUPPORTED", f"unsupported rank method {method}")


def _rank_order(metric, descending: bool, table: str) -> exp.Order:
    policy = current_semantic_policy()
    method = policy.ranking.method if policy else "row_number"
    null_order = policy.ranking.metric_null_order if policy else "engine_default"
    if null_order == "exclude":
        raise DorisBackendError(
            "DORIS_RANK_NULL_POLICY_UNSUPPORTED",
            "rank NULL exclusion requires an explicit pre-rank filter",
        )
    expressions = []
    if metric is not None:
        kwargs = {"this": metric, "desc": descending}
        if null_order == "first":
            kwargs["nulls_first"] = True
        elif null_order == "last":
            kwargs["nulls_first"] = False
        expressions.append(exp.Ordered(**kwargs))
    if method == "row_number":
        tie_breakers = policy.ranking.tie_breakers if policy else ("mktcode", "tgtcode")
        expressions.extend(
            exp.Ordered(
                this=exp.column(name, table=table, quoted=True),
                desc=False,
                nulls_first=True,
            )
            for name in tie_breakers
        )
    return exp.Order(expressions=expressions)


def _temporal_metric_predicate(plan: PhysicalTemporal, metrics_name: str):
    metric = exp.column("metric_value", table=metrics_name, quoted=True)
    total = exp.column("total_buckets", table=metrics_name, quoted=True)
    non_empty = exp.GT(this=total, expression=exp.convert(0))
    if plan.every:
        comparison = (exp.EQ if plan.comparator == "=" else exp.NEQ)(this=metric, expression=total)
        return exp.and_(non_empty, comparison)
    if plan.maximum is not None or plan.comparator == "between":
        return exp.and_(
            exp.GTE(this=metric, expression=exp.convert(plan.threshold)),
            exp.LTE(this=metric, expression=exp.convert(plan.maximum)),
        )
    comparator = ">=" if plan.mode == "CONS" and plan.comparator == "=" else plan.comparator
    return _COMPARISON[comparator](this=metric, expression=exp.convert(plan.threshold))


def _replace_table(query: exp.Select, old_name: str, new_name: str) -> exp.Select:
    result = query.copy()
    for table in result.find_all(exp.Table):
        if table.name == old_name:
            table.set("this", exp.to_identifier(new_name, quoted=True))
    for column in result.find_all(exp.Column):
        if column.table == old_name:
            column.set("table", exp.to_identifier(new_name, quoted=True))
    return result


def _find_scan(plan: PhysicalPlan) -> PhysicalScan:
    current = plan
    while isinstance(current, (PhysicalFilter, PhysicalLimit)):
        current = current.input
    if not isinstance(current, PhysicalScan):
        raise DorisBackendError("DORIS_SCAN_UNAVAILABLE", "rank plan has no physical scan input")
    return current


def _find_relation(plan: PhysicalPlan):
    current = plan
    while isinstance(current, (PhysicalFilter, PhysicalLimit)):
        current = current.input
    if isinstance(
        current,
        (PhysicalScan, PhysicalTableScan, PhysicalJoin, PhysicalPrefixJoin),
    ):
        return current
    raise DorisBackendError("DORIS_RELATION_UNAVAILABLE", "plan has no renderable physical relation")


def _stable_alias(relation) -> str:
    if isinstance(relation, PhysicalScan):
        return "anchor" if relation.anchor_resource_id else "q"
    if isinstance(relation, PhysicalTableScan):
        return relation.resource_id
    if isinstance(relation, PhysicalJoin):
        root, _ = _flatten_join(relation)
        return root.resource_id
    if isinstance(relation, PhysicalPrefixJoin):
        return "prefix_values"
    raise DorisBackendError("DORIS_RELATION_UNAVAILABLE", "plan has no stable output alias")


def _render_expr(expression, catalog: PhysicalCatalog, scan: Optional[PhysicalPlan] = None):
    if isinstance(expression, PhysicalPrefixRef):
        return exp.column(expression.alias, table="prefix_values", quoted=True)
    if isinstance(expression, PhysicalProjectedRef):
        return exp.column(expression.alias, table="event_rows", quoted=True)
    if isinstance(expression, PhysicalEventRef):
        return exp.column(expression.alias, table="event_rows", quoted=True)
    if isinstance(expression, PhysicalAggregateRef):
        return exp.column(
            expression.measure_alias,
            table=expression.relation_alias,
            quoted=True,
        )
    if isinstance(expression, PhysicalColumn):
        table_alias = _expression_alias(expression.resource_id, scan)
        return exp.column(expression.column, table=table_alias, quoted=True)
    if isinstance(expression, PhysicalLiteral):
        return exp.convert(expression.value)
    if isinstance(expression, PhysicalUnary):
        if expression.op != "negate":
            raise DorisBackendError("DORIS_OPERATOR_UNSUPPORTED", f"unsupported unary operator {expression.op}")
        return exp.Neg(this=_render_expr(expression.operand, catalog, scan))
    if isinstance(expression, PhysicalNot):
        return exp.Not(this=exp.Paren(this=_render_expr(expression.operand, catalog, scan)))
    if isinstance(expression, PhysicalNullIf):
        return exp.Nullif(
            this=_render_expr(expression.expression, catalog, scan),
            expression=_render_expr(expression.null_value, catalog, scan),
        )
    if isinstance(expression, PhysicalCoalesce):
        rendered = [_render_expr(item, catalog, scan) for item in expression.expressions]
        return exp.Coalesce(this=rendered[0], expressions=rendered[1:])
    if isinstance(expression, PhysicalAbs):
        return exp.Abs(this=_render_expr(expression.expression, catalog, scan))
    if isinstance(expression, PhysicalGreatest):
        rendered = [_render_expr(item, catalog, scan) for item in expression.expressions]
        return exp.Greatest(this=rendered[0], expressions=rendered[1:])
    if isinstance(expression, PhysicalIn):
        return exp.In(
            this=_render_expr(expression.expression, catalog, scan),
            expressions=[_render_expr(value, catalog, scan) for value in expression.values],
        )
    if isinstance(expression, PhysicalExternalExists):
        if scan is None:
            raise DorisBackendError(
                "DORIS_EXTERNAL_LOOKUP_CONTEXT_MISSING",
                "external membership lookup requires a scan context",
            )
        lookup = catalog.resource(expression.lookup_resource_id)
        alias = "external_lookup"
        table = exp.table_(lookup.table, db=lookup.database, quoted=True, alias=alias)
        anchor_alias = _expression_alias(expression.anchor_resource_id, scan)
        predicate = exp.and_(
            exp.EQ(
                this=exp.column("mktcode", table=alias, quoted=True),
                expression=exp.column("mktcode", table=anchor_alias, quoted=True),
            ),
            exp.EQ(
                this=exp.column("tgtcode", table=alias, quoted=True),
                expression=exp.column("tgtcode", table=anchor_alias, quoted=True),
            ),
        )
        for column, value in expression.filters:
            predicate = exp.and_(
                predicate,
                exp.EQ(
                    this=exp.column(column, table=alias, quoted=True),
                    expression=_render_expr(value, catalog, scan),
                ),
            )
        query = exp.select(exp.convert(1)).from_(table).where(predicate)
        return exp.Exists(this=query)
    if isinstance(expression, PhysicalLatestValue):
        resource = catalog.resource(expression.resource_id)
        table = exp.table_(resource.table, db=resource.database, quoted=True, alias="q_latest")
        query = exp.select(exp.Max(this=exp.column(expression.column, table="q_latest", quoted=True))).from_(table)
        return exp.Subquery(this=query)
    if isinstance(expression, PhysicalNthLatestValue):
        resource = catalog.resource(expression.resource_id)
        alias = "q_session"
        column = exp.column(expression.column, table=alias, quoted=True)
        table = exp.table_(resource.table, db=resource.database, quoted=True, alias=alias)
        query = (
            exp.select(column.copy())
            .from_(table)
            .group_by(column.copy())
            .order_by(exp.Ordered(this=column.copy(), desc=True))
            .limit(1)
            .offset(expression.offset)
        )
        return exp.Subquery(this=query)
    if isinstance(expression, PhysicalRecentSessions):
        calendar_resource_id = (
            expression.anchor_resource_id or expression.resource_id
        )
        resource = catalog.resource(calendar_resource_id)
        alias = "calendar_sessions"
        column = exp.column(expression.column, table=alias, quoted=True)
        table = exp.table_(resource.table, db=resource.database, quoted=True, alias=alias)
        query = (
            exp.select(column.copy())
            .from_(table)
            .group_by(column.copy())
            .order_by(exp.Ordered(this=column.copy(), desc=True))
            .limit(expression.amount)
        )
        if expression.offset:
            query = query.offset(expression.offset)
        return exp.In(
            this=exp.column(
                expression.column,
                table=_expression_alias(expression.resource_id, scan),
                quoted=True,
            ),
            query=exp.Subquery(this=query),
        )
    if isinstance(expression, PhysicalDynamicDateRange):
        if scan is None:
            raise DorisBackendError(
                "DORIS_DATE_CONTEXT_MISSING",
                "dynamic date range requires a scan context",
            )
        column = exp.column(
            expression.column,
            table=_expression_alias(expression.resource_id, scan),
            quoted=True,
        )
        lower, upper, validity = _dynamic_date_bounds(
            catalog,
            expression.resource_id,
            expression.range_kind,
            expression.unit,
            expression.amount,
            expression.offset,
            expression.month,
            expression.day,
            expression.end_month,
            expression.anchor_resource_id,
            expression.weekday_start,
            expression.weekday_end,
        )
        predicate = exp.and_(
            exp.GTE(this=column.copy(), expression=lower),
            exp.LTE(this=column.copy(), expression=upper),
        )
        return exp.and_(predicate, validity) if validity is not None else predicate
    if isinstance(expression, PhysicalSessionBoundaryRange):
        if scan is None:
            raise DorisBackendError(
                "DORIS_DATE_CONTEXT_MISSING",
                "session boundary range requires a scan context",
            )
        calendar_resource_id = (
            expression.anchor_resource_id or expression.resource_id
        )
        resource = catalog.resource(calendar_resource_id)
        alias = "boundary_sessions"
        calendar_column = exp.column(expression.column, table=alias, quoted=True)
        if expression.boundary_kind == "period":
            boundary = _date_shift(
                _date_trunc(
                    _latest_resource_anchor(catalog, calendar_resource_id),
                    expression.unit,
                ),
                expression.offset,
                expression.unit,
            )
            validity = None
        elif expression.boundary_kind == "anchor":
            boundary, _, validity = _dynamic_date_bounds(
                catalog,
                calendar_resource_id,
                "anchor_calendar",
                "day",
                1,
                expression.offset,
                expression.month,
                expression.day,
            )
        else:
            boundary = exp.convert(expression.boundary_date)
            validity = None
        comparator = exp.LT if expression.direction == "before" else exp.GT
        query = (
            exp.select(calendar_column.copy())
            .from_(
                exp.table_(
                    resource.table,
                    db=resource.database,
                    quoted=True,
                    alias=alias,
                )
            )
            .where(
                exp.and_(
                    comparator(this=calendar_column.copy(), expression=boundary),
                    validity,
                )
                if validity is not None
                else comparator(this=calendar_column.copy(), expression=boundary)
            )
            .group_by(calendar_column.copy())
            .order_by(
                exp.Ordered(
                    this=calendar_column.copy(),
                    desc=expression.direction == "before",
                )
            )
            .limit(expression.amount)
        )
        return exp.In(
            this=exp.column(
                expression.column,
                table=_expression_alias(expression.resource_id, scan),
                quoted=True,
            ),
            query=exp.Subquery(this=query),
        )
    if isinstance(expression, PhysicalPrefixAverage):
        if scan is None:
            raise DorisBackendError("DORIS_PREFIX_CONTEXT_MISSING", "prefix average requires a scan context")
        resource = catalog.resource(expression.resource_id)
        current = exp.table_(resource.table, db=resource.database, quoted=True, alias="p")
        previous = exp.table_(resource.table, db=resource.database, quoted=True, alias="p_prev")
        previous_join = exp.and_(
            exp.EQ(this=exp.column("mktcode", table="p_prev", quoted=True), expression=exp.column("mktcode", table="p", quoted=True)),
            exp.EQ(this=exp.column("tgtcode", table="p_prev", quoted=True), expression=exp.column("tgtcode", table="p", quoted=True)),
            exp.EQ(
                this=exp.column("row_no", table="p_prev", quoted=True),
                expression=exp.Sub(this=exp.column("row_no", table="p", quoted=True), expression=exp.convert(expression.window)),
            ),
        )
        scan_alias = "anchor" if scan.anchor_resource_id else "q"
        correlation = exp.and_(
            *(
                exp.EQ(
                    this=exp.column(key, table="p", quoted=True),
                    expression=exp.column(key, table=scan_alias, quoted=True),
                )
                for key in ("mktcode", "tgtcode", "bizdate")
            )
        )
        average = _prefix_average_expression(expression, "p", "p_prev")
        query = exp.select(average).from_(current).join(previous, on=previous_join, join_type="LEFT").where(correlation)
        return exp.Subquery(this=query)
    if isinstance(expression, PhysicalBinary):
        try:
            operator = _BINARY[expression.op.lower()]
        except KeyError as exc:
            raise DorisBackendError("DORIS_OPERATOR_UNSUPPORTED", f"unsupported binary operator {expression.op}") from exc
        left = _render_expr(expression.left, catalog, scan)
        right = _render_expr(expression.right, catalog, scan)
        if isinstance(expression.left, PhysicalBinary):
            left = exp.Paren(this=left)
        if isinstance(expression.right, PhysicalBinary):
            right = exp.Paren(this=right)
        return operator(
            this=left,
            expression=right,
        )
    if isinstance(expression, PhysicalComparison):
        exists_predicate = _render_exists_boolean_comparison(
            expression,
            catalog,
            scan,
        )
        if exists_predicate is not None:
            return exists_predicate
        try:
            operator = _COMPARISON[expression.op]
        except KeyError as exc:
            raise DorisBackendError("DORIS_OPERATOR_UNSUPPORTED", f"unsupported comparison operator {expression.op}") from exc
        left = _render_expr(expression.left, catalog, scan)
        right = _render_expr(expression.right, catalog, scan)
        if isinstance(expression.left, PhysicalBinary):
            left = exp.Paren(this=left)
        if isinstance(expression.right, PhysicalBinary):
            right = exp.Paren(this=right)
        return operator(
            this=left,
            expression=right,
        )
    raise DorisBackendError("DORIS_EXPRESSION_UNSUPPORTED", f"unsupported physical expression {type(expression).__name__}")


def _render_exists_boolean_comparison(expression, catalog, scan):
    if expression.op not in {"=", "!="}:
        return None
    pairs = (
        (expression.left, expression.right),
        (expression.right, expression.left),
    )
    for candidate, literal in pairs:
        if not (
            isinstance(candidate, PhysicalExternalExists)
            and isinstance(literal, PhysicalLiteral)
            and isinstance(literal.value, bool)
        ):
            continue
        rendered = _render_expr(candidate, catalog, scan)
        expected = literal.value if expression.op == "=" else not literal.value
        return rendered if expected else exp.Not(this=rendered)
    return None


def _expression_alias(resource_id: str, relation: Optional[PhysicalPlan]) -> str:
    if isinstance(relation, PhysicalScan):
        return "anchor" if resource_id == relation.anchor_resource_id else "q"
    if isinstance(relation, PhysicalTableScan):
        if resource_id != relation.resource_id:
            raise DorisBackendError(
                "DORIS_COLUMN_RESOURCE_UNAVAILABLE",
                f"resource {resource_id} is not present in table scan {relation.resource_id}",
            )
        return relation.resource_id
    if isinstance(relation, PhysicalJoin):
        root, joins = _flatten_join(relation)
        available = {root.resource_id, *(right.resource_id for right, _, _ in joins)}
        if resource_id not in available:
            raise DorisBackendError(
                "DORIS_COLUMN_RESOURCE_UNAVAILABLE",
                f"resource {resource_id} is not present in physical join",
            )
        return resource_id
    if isinstance(relation, PhysicalPrefixJoin):
        return "prefix_values"
    return "q"
