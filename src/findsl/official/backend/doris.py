from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlglot import exp

from ..physical.catalog import PhysicalCatalog
from ..physical.ir import (
    PhysicalAbs,
    PhysicalBinary,
    PhysicalAggregateGroup,
    PhysicalAggregateRank,
    PhysicalAggregateRef,
    PhysicalCoalesce,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalCompositeAggregate,
    PhysicalFilter,
    PhysicalDynamicDateRange,
    PhysicalEventFilter,
    PhysicalEventRef,
    PhysicalExtreme,
    PhysicalGroupedAggregate,
    PhysicalGreatest,
    PhysicalIn,
    PhysicalJoin,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalNullIf,
    PhysicalNot,
    PhysicalNthLatestValue,
    PhysicalPlan,
    PhysicalPrefixAverage,
    PhysicalPattern,
    PhysicalPosition,
    PhysicalProjectedRef,
    PhysicalRank,
    PhysicalRecentSessions,
    PhysicalScan,
    PhysicalSessionBoundaryRange,
    PhysicalTableScan,
    PhysicalSetOperation,
    PhysicalTemporal,
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
    if isinstance(plan, PhysicalFilter):
        return _render_plan(plan.input, catalog, cte_prefix).where(
            _render_expr(plan.predicate, catalog, _find_relation(plan.input))
        )
    if isinstance(plan, PhysicalLimit):
        query = _render_plan(plan.input, catalog, cte_prefix).limit(plan.count)
        return query.offset(plan.offset) if plan.offset else query
    if isinstance(plan, PhysicalRank):
        inner = _render_plan(plan.input, catalog, cte_prefix)
        relation = _find_relation(plan.input)
        stable_alias = _stable_alias(relation)
        order = exp.Order(
            expressions=[
                exp.Ordered(
                    this=_render_expr(plan.expression, catalog, relation),
                    desc=plan.direction == "desc",
                ),
                exp.Ordered(
                    this=exp.column("mktcode", table=stable_alias, quoted=True),
                    desc=False,
                    nulls_first=True,
                ),
                exp.Ordered(
                    this=exp.column("tgtcode", table=stable_alias, quoted=True),
                    desc=False,
                    nulls_first=True,
                ),
            ]
        )
        window = exp.Window(
            this=exp.RowNumber(),
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
        comparator = _COMPARISON[plan.comparator](
            this=exp.column("__rank_value", table="ranked", quoted=True),
            expression=_render_rank_bound(plan.bound, plan.percentage, "ranked"),
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
    if isinstance(plan, PhysicalTemporal):
        return _render_temporal(plan, catalog, cte_prefix)
    if isinstance(plan, PhysicalSetOperation):
        return _render_set_operation(plan, catalog, cte_prefix)
    raise DorisBackendError("DORIS_PLAN_UNSUPPORTED", f"unsupported physical node {type(plan).__name__}")


def _render_event_filter(
    plan: PhysicalEventFilter,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
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

    for event in plan.events:
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
                this=exp.Sub(this=value.copy(), expression=minimum.copy()),
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

    for projection in plan.projections:
        source = source.select(
            _render_expr(projection.expression, catalog, relation).as_(
                projection.alias,
                quoted=True,
            ),
            append=True,
        )

    alias = "event_rows"
    rows = source.subquery(alias=alias)
    outer = exp.select(
        *(exp.column(name, table=alias, quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
    ).from_(rows)
    predicate = _render_expr(plan.predicate, catalog)
    for constraint in plan.result_constraints:
        rendered = _render_expr(constraint, catalog, relation)
        predicate = exp.and_(
            predicate,
            _retarget_event_result_columns(rendered, alias, catalog),
        )
    return outer.where(predicate)


def _event_window_aggregate(value, aggregate, partition, order, lookback_sessions):
    frame_start = (
        "UNBOUNDED"
        if lookback_sessions is None
        else exp.Literal.number(lookback_sessions - 1)
    )
    return exp.Window(
        this=aggregate(this=value.copy()),
        partition_by=[item.copy() for item in partition],
        order=order.copy(),
        spec=exp.WindowSpec(
            kind="ROWS",
            start=frame_start,
            start_side="PRECEDING",
            end="CURRENT ROW",
        ),
    )


def _retarget_event_result_columns(expression, alias: str, catalog: PhysicalCatalog):
    resource_aliases = {resource.resource_id for resource in catalog.resources}
    resource_aliases.update({"q", "anchor"})
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
    aggregate = {
        "sum": exp.Sum,
        "avg": exp.Avg,
        "max": exp.Max,
        "min": exp.Min,
    }[plan.function](
        this=_render_expr(plan.measure, catalog, relation)
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


def _render_aggregate_rank(
    plan: PhysicalAggregateRank,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(plan.input, catalog, cte_prefix)
    relation = _find_relation(plan.input)
    stable_alias = _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    aggregate = {
        "sum": exp.Sum,
        "avg": exp.Avg,
        "max": exp.Max,
        "min": exp.Min,
    }[plan.function](
        this=_render_expr(plan.measure, catalog, relation)
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
    order = exp.Order(
        expressions=[
            exp.Ordered(
                this=exp.column("metric_value", table="aggregate_rows", quoted=True),
                desc=plan.direction == "desc",
            ),
            exp.Ordered(
                this=exp.column("mktcode", table="aggregate_rows", quoted=True),
                desc=False,
                nulls_first=True,
            ),
            exp.Ordered(
                this=exp.column("tgtcode", table="aggregate_rows", quoted=True),
                desc=False,
                nulls_first=True,
            ),
        ]
    )
    ranked = exp.select(
        *(exp.column(key, table="aggregate_rows", quoted=True) for key in keys),
        exp.column("metric_value", table="aggregate_rows", quoted=True),
        exp.Window(this=exp.RowNumber(), order=order).as_("__rank_value"),
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
        _COMPARISON[plan.comparator](
            this=exp.column("__rank_value", table="aggregate_ranked", quoted=True),
            expression=_render_rank_bound(
                plan.bound,
                plan.percentage,
                "aggregate_ranked",
            ),
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
        query = query.join(scalar_rows, join_type="CROSS")
    return query.where(_render_expr(plan.predicate, catalog, anchor_relation))


def _render_aggregate_group(
    group: PhysicalAggregateGroup,
    catalog: PhysicalCatalog,
    cte_prefix: str = "",
) -> exp.Select:
    source = _render_plan(group.input, catalog, cte_prefix)
    relation = _find_relation(group.input)
    stable_alias = _stable_alias(relation)
    keys = ("mktcode", "tgtcode")
    functions = {
        "sum": exp.Sum,
        "avg": exp.Avg,
        "max": exp.Max,
        "min": exp.Min,
    }
    measures = [
        functions[measure.function](
            this=_render_expr(measure.expression, catalog, relation)
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


def _render_named_scalar(scalar, catalog: PhysicalCatalog, cte_prefix: str = "") -> exp.Select:
    source = _render_plan(scalar.input, catalog, cte_prefix)
    relation = _find_relation(scalar.input)
    source.set(
        "expressions",
        [
            _render_expr(scalar.expression, catalog, relation).as_(
                scalar.value_alias,
                quoted=True,
            )
        ],
    )
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
    scan = _find_scan(plan.input)
    if not isinstance(plan.input, PhysicalScan):
        raise DorisBackendError(
            "DORIS_TEMPORAL_INPUT_UNSUPPORTED",
            "temporal plan currently requires a direct physical scan input",
        )
    stable_alias = "anchor" if scan.anchor_resource_id else "q"
    keys = ("mktcode", "tgtcode")
    source_rows_name = f"{cte_prefix}source_rows"
    eligible_rows_name = f"{cte_prefix}eligible_rows"
    bucket_rows_name = f"{cte_prefix}bucket_rows"
    sequenced_rows_name = f"{cte_prefix}sequenced_rows"
    matched_rows_name = f"{cte_prefix}matched_rows"
    runs_name = f"{cte_prefix}runs"
    metrics_name = f"{cte_prefix}temporal_metrics"
    qualified_name = f"{cte_prefix}qualified"
    source = _render_plan(scan, catalog, cte_prefix)
    matched = exp.Case(
        ifs=[
            exp.If(
                this=_render_expr(plan.predicate, catalog, scan),
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
                    scan.anchor_resource_id or scan.resource_id,
                    "bizdate",
                    plan.window.boundary_direction,
                    plan.window.boundary_kind,
                    plan.window.lookback_sessions or 1,
                    unit=plan.window.calendar_unit,
                    offset=plan.window.calendar_offset,
                    boundary_date=plan.window.boundary_date,
                ),
                catalog,
                scan,
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
            scan.anchor_resource_id or scan.resource_id,
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
    elif plan.window.kind in {"dynamic_period", "anchor_calendar"}:
        amount = plan.window.calendar_amount or 1
        unit = plan.window.calendar_unit
        if unit is None:
            raise DorisBackendError(
                "DORIS_TEMPORAL_WINDOW_INVALID",
                "dynamic calendar window is missing its unit",
            )
        lower, upper, validity = _dynamic_date_bounds(
            catalog,
            scan.anchor_resource_id or scan.resource_id,
            "period" if plan.window.kind == "dynamic_period" else "anchor_calendar",
            unit,
            amount,
            plan.window.calendar_offset,
            plan.window.anchor_month,
            plan.window.anchor_day,
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

    anchor_resource = catalog.resource(scan.anchor_resource_id or scan.resource_id)
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
):
    anchor = _latest_resource_anchor(catalog, resource_id)
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
    if isinstance(current, (PhysicalScan, PhysicalTableScan, PhysicalJoin)):
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
    raise DorisBackendError("DORIS_RELATION_UNAVAILABLE", "plan has no stable output alias")


def _render_expr(expression, catalog: PhysicalCatalog, scan: Optional[PhysicalPlan] = None):
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
        resource = catalog.resource(expression.resource_id)
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
        resource = catalog.resource(expression.resource_id)
        alias = "boundary_sessions"
        calendar_column = exp.column(expression.column, table=alias, quoted=True)
        if expression.boundary_kind == "period":
            boundary = _date_shift(
                _date_trunc(
                    _latest_resource_anchor(catalog, expression.resource_id),
                    expression.unit,
                ),
                expression.offset,
                expression.unit,
            )
        else:
            boundary = exp.convert(expression.boundary_date)
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
            .where(comparator(this=calendar_column.copy(), expression=boundary))
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
        sum_delta = exp.Sub(
            this=exp.column(expression.sum_column, table="p", quoted=True),
            expression=exp.Coalesce(
                this=exp.column(expression.sum_column, table="p_prev", quoted=True),
                expressions=[exp.convert(0)],
            ),
        )
        count_delta = exp.Sub(
            this=exp.column(expression.count_column, table="p", quoted=True),
            expression=exp.Coalesce(
                this=exp.column(expression.count_column, table="p_prev", quoted=True),
                expressions=[exp.convert(0)],
            ),
        )
        average = exp.Div(
            this=exp.Mul(this=exp.Paren(this=sum_delta), expression=exp.convert(1.0)),
            expression=exp.Nullif(this=count_delta, expression=exp.convert(0)),
        )
        if expression.scale_divisor != 1.0:
            average = exp.Div(this=average, expression=exp.convert(expression.scale_divisor))
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
    return "q"
