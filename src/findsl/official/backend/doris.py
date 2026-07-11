from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlglot import exp

from ..physical.catalog import PhysicalCatalog
from ..physical.ir import (
    PhysicalBinary,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalFilter,
    PhysicalIn,
    PhysicalLatestValue,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalPlan,
    PhysicalPrefixAverage,
    PhysicalRank,
    PhysicalScan,
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


def render_doris(plan: PhysicalPlan, catalog: PhysicalCatalog) -> DorisRenderResult:
    validate_physical_plan(plan, catalog)
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
    raise DorisBackendError("DORIS_PLAN_UNSUPPORTED", f"unsupported physical node {type(plan).__name__}")


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
        return operator(
            this=_render_expr(expression.left, catalog, scan),
            expression=_render_expr(expression.right, catalog, scan),
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
