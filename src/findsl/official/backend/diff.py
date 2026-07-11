from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Sequence, Tuple

import sqlglot
from sqlglot import exp


@dataclass(frozen=True)
class DorisStructuralSignature:
    tables: Tuple[str, ...]
    projections: Tuple[str, ...]
    operators: Tuple[str, ...]
    predicate: str
    limit: str
    offset: str


@dataclass(frozen=True)
class DorisStructuralDiff:
    equivalent: bool
    legacy: DorisStructuralSignature
    shadow: DorisStructuralSignature
    differences: Tuple[str, ...]


_OPERATORS = (
    exp.Add, exp.Sub, exp.Mul, exp.Div, exp.And, exp.Or, exp.Xor,
    exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE,
    exp.Between, exp.Window, exp.RowNumber,
)


def compare_doris_sql(legacy_sql: str, shadow_sql: str) -> DorisStructuralDiff:
    legacy = structural_signature(legacy_sql)
    shadow = structural_signature(shadow_sql)
    differences = tuple(
        name
        for name in ("tables", "projections", "operators", "predicate", "limit", "offset")
        if getattr(legacy, name) != getattr(shadow, name)
    )
    return DorisStructuralDiff(not differences, legacy, shadow, differences)


def structural_signature(sql: str) -> DorisStructuralSignature:
    statement = sqlglot.parse_one(sql, read="doris")
    if not isinstance(statement, exp.Select):
        raise ValueError("structural diff requires a Doris SELECT")
    tables = tuple(sorted(_qualified_table(table) for table in statement.find_all(exp.Table)))
    projections = tuple(_projection_name(item) for item in statement.expressions)
    operators = tuple(sorted(type(item).__name__ for item in statement.walk() if isinstance(item, _OPERATORS)))
    where = statement.args.get("where")
    predicate = _alias_free_sql(where.this) if where is not None else ""
    limit = _argument_sql(statement.args.get("limit"), "expression")
    offset = _argument_sql(statement.args.get("offset"), "expression")
    return DorisStructuralSignature(tables, projections, operators, predicate, limit, offset)


def hash_result_rows(rows: Iterable[Sequence[object]], *, ordered: bool) -> str:
    encoded = [json.dumps([_canonical_cell(value) for value in row], ensure_ascii=False, separators=(",", ":")) for row in rows]
    if not ordered:
        encoded.sort()
    payload = json.dumps({"ordered": ordered, "rows": encoded}, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _qualified_table(table: exp.Table) -> str:
    parts = [part for part in (table.catalog, table.db, table.name) if part]
    return ".".join(parts)


def _projection_name(expression: exp.Expression) -> str:
    return expression.alias_or_name or _alias_free_sql(expression)


def _alias_free_sql(expression: exp.Expression) -> str:
    normalized = expression.copy()
    for column in normalized.find_all(exp.Column):
        column.set("table", None)
        identifier = column.args.get("this")
        if isinstance(identifier, exp.Identifier):
            identifier.set("quoted", False)
    return normalized.sql(dialect="doris", normalize=True)


def _argument_sql(expression, child: str) -> str:
    if expression is None:
        return ""
    value = expression.args.get(child)
    return value.sql(dialect="doris") if value is not None else ""


def _canonical_cell(value):
    if value is None:
        return ["null", None]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, (float, Decimal)):
        return ["number", str(value)]
    if isinstance(value, (date, datetime)):
        return ["time", value.isoformat()]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    return ["string", str(value)]
