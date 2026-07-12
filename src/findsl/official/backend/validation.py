from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import sqlglot
from sqlglot import exp

from ...doris_sql import DorisSqlValidationResult, validate_doris_select_sql
from ...registry import Registry
from ..physical.catalog import PhysicalCatalog


@dataclass(frozen=True)
class DorisAstValidation:
    passed: bool
    issues: Tuple[str, ...]
    round_trip_stable: bool
    safety: DorisSqlValidationResult


def validate_doris_ast(sql: str, catalog: PhysicalCatalog) -> DorisAstValidation:
    issues = []
    statements = sqlglot.parse(sql, read="doris")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        issues.append("DORIS_AST_NOT_SINGLE_SELECT")

    rendered = statements[0].sql(dialect="doris") if statements else ""
    round_trip_stable = rendered == sql
    if not round_trip_stable:
        issues.append("DORIS_AST_ROUND_TRIP_UNSTABLE")

    cte_names = {cte.alias_or_name for statement in statements for cte in statement.find_all(exp.CTE)}
    registry_tables = {
        resource.resource_id: {"physical": resource.table}
        for resource in catalog.resources
    }
    registry_tables.update(
        {f"cte_{index}": {"physical": name} for index, name in enumerate(sorted(cte_names))}
    )
    allowed_registry = Registry(
        indicators={},
        tables=registry_tables,
        functions={},
    )
    safety = validate_doris_select_sql(sql, allowed_registry)
    if not safety.passed:
        issues.extend(item.code for item in safety.issues)

    parsed_tables = {
        table.name
        for statement in statements
        for table in statement.find_all(exp.Table)
        if table.name not in cte_names
    }
    allowed_tables = {resource.table for resource in catalog.resources}
    if not parsed_tables.issubset(allowed_tables):
        issues.append("DORIS_AST_UNKNOWN_RESOURCE")
    return DorisAstValidation(not issues, tuple(dict.fromkeys(issues)), round_trip_stable, safety)
