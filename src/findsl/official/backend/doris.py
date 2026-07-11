from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp

from ..physical.catalog import PhysicalCatalog
from ..physical.ir import (
    PhysicalBinary,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalFilter,
    PhysicalLimit,
    PhysicalLiteral,
    PhysicalPlan,
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
        projections = tuple(exp.column(name, table="q", quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
        table = exp.table_(resource.table, db=resource.database, quoted=True, alias="q")
        query = exp.select(*projections).from_(table)
        if plan.partition_predicate is not None:
            query = query.where(_render_expr(plan.partition_predicate))
        return query
    if isinstance(plan, PhysicalFilter):
        return _render_plan(plan.input, catalog).where(_render_expr(plan.predicate))
    if isinstance(plan, PhysicalLimit):
        query = _render_plan(plan.input, catalog).limit(plan.count)
        return query.offset(plan.offset) if plan.offset else query
    raise DorisBackendError("DORIS_PLAN_UNSUPPORTED", f"unsupported physical node {type(plan).__name__}")


def _render_expr(expression):
    if isinstance(expression, PhysicalColumn):
        return exp.column(expression.column, table="q", quoted=True)
    if isinstance(expression, PhysicalLiteral):
        return exp.convert(expression.value)
    if isinstance(expression, PhysicalBinary):
        try:
            operator = _BINARY[expression.op.lower()]
        except KeyError as exc:
            raise DorisBackendError("DORIS_OPERATOR_UNSUPPORTED", f"unsupported binary operator {expression.op}") from exc
        return operator(this=_render_expr(expression.left), expression=_render_expr(expression.right))
    if isinstance(expression, PhysicalComparison):
        try:
            operator = _COMPARISON[expression.op]
        except KeyError as exc:
            raise DorisBackendError("DORIS_OPERATOR_UNSUPPORTED", f"unsupported comparison operator {expression.op}") from exc
        return operator(this=_render_expr(expression.left), expression=_render_expr(expression.right))
    raise DorisBackendError("DORIS_EXPRESSION_UNSUPPORTED", f"unsupported physical expression {type(expression).__name__}")
