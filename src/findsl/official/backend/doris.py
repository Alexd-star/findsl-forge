from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlglot import exp

from ..physical.catalog import PhysicalCatalog
from ..physical.ir import (
    PhysicalBinary,
    PhysicalCoalesce,
    PhysicalColumn,
    PhysicalComparison,
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


def _render_plan(plan: PhysicalPlan, catalog: PhysicalCatalog) -> exp.Select:
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
        return _render_plan(plan.input, catalog).where(
            _render_expr(plan.predicate, catalog, _find_scan(plan.input))
        )
    if isinstance(plan, PhysicalLimit):
        query = _render_plan(plan.input, catalog).limit(plan.count)
        return query.offset(plan.offset) if plan.offset else query
    if isinstance(plan, PhysicalRank):
        inner = _render_plan(plan.input, catalog)
        scan = _find_scan(plan.input)
        stable_alias = "anchor" if scan.anchor_resource_id else "q"
        order = exp.Order(
            expressions=[
                exp.Ordered(
                    this=_render_expr(plan.expression, catalog, scan),
                    desc=plan.direction == "desc",
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
        ranked = inner.subquery(alias="ranked")
        outer = exp.select(
            *(exp.column(name, table="ranked", quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
        ).from_(ranked)
        comparator = _COMPARISON[plan.comparator](
            this=exp.column("__rank_value", table="ranked", quoted=True),
            expression=_render_expr(plan.bound, catalog, scan),
        )
        return outer.where(comparator)
    if isinstance(plan, PhysicalTemporal):
        return _render_temporal(plan, catalog)
    raise DorisBackendError("DORIS_PLAN_UNSUPPORTED", f"unsupported physical node {type(plan).__name__}")


def _render_temporal(plan: PhysicalTemporal, catalog: PhysicalCatalog) -> exp.Select:
    scan = _find_scan(plan.input)
    if not isinstance(plan.input, PhysicalScan):
        raise DorisBackendError(
            "DORIS_TEMPORAL_INPUT_UNSUPPORTED",
            "temporal plan currently requires a direct physical scan input",
        )
    stable_alias = "anchor" if scan.anchor_resource_id else "q"
    keys = ("mktcode", "tgtcode")
    source = _render_plan(scan, catalog)
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

    needs_session_limit = plan.window.kind in {"recent_sessions", "latest_session"}
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

    ctes = [("source_rows", source)]
    relation_name = "source_rows"
    if needs_session_limit:
        lookback = plan.window.lookback_sessions or 1
        eligible = exp.select(exp.Star()).from_(exp.table_("source_rows", quoted=True)).where(
            exp.LTE(
                this=exp.column("lookback_row", table="source_rows", quoted=True),
                expression=exp.convert(lookback),
            )
        )
        ctes.append(("eligible_rows", eligible))
        relation_name = "eligible_rows"

    if plan.every or plan.mode == "EXIST":
        metrics = _render_exist_metrics(relation_name, keys)
    else:
        matched_rows = exp.select(
            *(exp.column(name, table=relation_name, quoted=True) for name in (*keys, "bizdate", "all_seq"))
        ).from_(exp.table_(relation_name, quoted=True)).where(
            exp.EQ(
                this=exp.column("matched", table=relation_name, quoted=True),
                expression=exp.convert(1),
            )
        )
        matched_rows = matched_rows.select(
            _row_number(relation_name, keys, "bizdate").as_("matched_seq", quoted=True),
            append=True,
        )
        ctes.append(("matched_rows", matched_rows))

        island = exp.Sub(
            this=exp.column("all_seq", table="matched_rows", quoted=True),
            expression=exp.column("matched_seq", table="matched_rows", quoted=True),
        )
        runs = exp.select(
            *(exp.column(name, table="matched_rows", quoted=True) for name in keys),
            island.as_("run_group", quoted=True),
            exp.Count(this=exp.Star()).as_("run_length", quoted=True),
        ).from_(exp.table_("matched_rows", quoted=True)).group_by(
            *(exp.column(name, table="matched_rows", quoted=True) for name in keys),
            island,
        )
        ctes.append(("runs", runs))
        metrics = exp.select(
            *(exp.column(name, table="runs", quoted=True) for name in keys),
            exp.Max(this=exp.column("run_length", table="runs", quoted=True)).as_("metric_value", quoted=True),
            exp.Count(this=exp.Star()).as_("total_buckets", quoted=True),
        ).from_(exp.table_("runs", quoted=True)).group_by(
            *(exp.column(name, table="runs", quoted=True) for name in keys)
        )

    if plan.mode == "CONS" and not plan.every:
        sequence_relation = relation_name
        sequence = exp.select(
            *(exp.column(name, table=sequence_relation, quoted=True) for name in (*keys, "bizdate", "matched")),
            _row_number(sequence_relation, keys, "bizdate").as_("all_seq", quoted=True),
        ).from_(exp.table_(sequence_relation, quoted=True))
        insert_at = 2 if needs_session_limit else 1
        ctes.insert(insert_at, ("sequenced_rows", sequence))
        for index, (name, query) in enumerate(ctes):
            if name == "matched_rows":
                ctes[index] = (name, _replace_table(query, relation_name, "sequenced_rows"))
        relation_name = "sequenced_rows"

    ctes.append(("temporal_metrics", metrics))
    qualified_predicate = _temporal_metric_predicate(plan)
    qualified = exp.select(
        *(exp.column(name, table="temporal_metrics", quoted=True) for name in keys)
    ).from_(exp.table_("temporal_metrics", quoted=True)).where(qualified_predicate)
    ctes.append(("qualified", qualified))

    anchor_resource = catalog.resource(scan.anchor_resource_id or scan.resource_id)
    anchor = exp.table_(
        anchor_resource.table,
        db=anchor_resource.database,
        quoted=True,
        alias="anchor_out",
    )
    qualified_table = exp.table_("qualified", quoted=True, alias="qualified")
    join_predicate = exp.and_(
        *(
            exp.EQ(
                this=exp.column(name, table="anchor_out", quoted=True),
                expression=exp.column(name, table="qualified", quoted=True),
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


def _render_exist_metrics(relation_name: str, keys) -> exp.Select:
    return exp.select(
        *(exp.column(name, table=relation_name, quoted=True) for name in keys),
        exp.Sum(this=exp.column("matched", table=relation_name, quoted=True)).as_("metric_value", quoted=True),
        exp.Count(this=exp.Star()).as_("total_buckets", quoted=True),
    ).from_(exp.table_(relation_name, quoted=True)).group_by(
        *(exp.column(name, table=relation_name, quoted=True) for name in keys)
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


def _temporal_metric_predicate(plan: PhysicalTemporal):
    metric = exp.column("metric_value", table="temporal_metrics", quoted=True)
    total = exp.column("total_buckets", table="temporal_metrics", quoted=True)
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


def _render_expr(expression, catalog: PhysicalCatalog, scan: Optional[PhysicalScan] = None):
    if isinstance(expression, PhysicalColumn):
        table_alias = "anchor" if scan and expression.resource_id == scan.anchor_resource_id else "q"
        return exp.column(expression.column, table=table_alias, quoted=True)
    if isinstance(expression, PhysicalLiteral):
        return exp.convert(expression.value)
    if isinstance(expression, PhysicalUnary):
        if expression.op != "negate":
            raise DorisBackendError("DORIS_OPERATOR_UNSUPPORTED", f"unsupported unary operator {expression.op}")
        return exp.Neg(this=_render_expr(expression.operand, catalog, scan))
    if isinstance(expression, PhysicalNullIf):
        return exp.Nullif(
            this=_render_expr(expression.expression, catalog, scan),
            expression=_render_expr(expression.null_value, catalog, scan),
        )
    if isinstance(expression, PhysicalCoalesce):
        rendered = [_render_expr(item, catalog, scan) for item in expression.expressions]
        return exp.Coalesce(this=rendered[0], expressions=rendered[1:])
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
        return operator(
            this=_render_expr(expression.left, catalog, scan),
            expression=_render_expr(expression.right, catalog, scan),
        )
    raise DorisBackendError("DORIS_EXPRESSION_UNSUPPORTED", f"unsupported physical expression {type(expression).__name__}")
