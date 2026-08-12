from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import sqlglot
from sqlglot import exp

from ...doris_sql import (
    DorisSqlIssue,
    DorisSqlValidationResult,
    validate_doris_select_sql,
)
from ...registry import Registry
from ..physical.catalog import PhysicalCatalog


@dataclass(frozen=True)
class DorisAstValidation:
    passed: bool
    issues: Tuple[str, ...]
    round_trip_checked: bool
    round_trip_stable: bool | None
    safety: DorisSqlValidationResult


def validate_doris_ast(
    ast: exp.Select,
    sql: str,
    catalog: PhysicalCatalog,
    *,
    verify_round_trip: bool,
) -> DorisAstValidation:
    issues = []
    statements = (ast,)
    round_trip_stable = None
    if verify_round_trip:
        parsed = sqlglot.parse(sql, read="doris")
        if len(parsed) != 1 or not isinstance(parsed[0], exp.Select):
            issues.append("DORIS_AST_NOT_SINGLE_SELECT")
        rendered = parsed[0].sql(dialect="doris") if parsed else ""
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
    safety = (
        validate_doris_select_sql(sql, allowed_registry)
        if verify_round_trip
        else _validate_generated_select_ast(ast, allowed_tables={resource.table for resource in catalog.resources}, cte_names=cte_names)
    )
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
    return DorisAstValidation(
        not issues,
        tuple(dict.fromkeys(issues)),
        verify_round_trip,
        round_trip_stable,
        safety,
    )


def _validate_generated_select_ast(
    ast: exp.Select,
    *,
    allowed_tables: set[str],
    cte_names: set[str],
) -> DorisSqlValidationResult:
    issues = []
    forbidden_types = (
        exp.Alter,
        exp.Command,
        exp.Create,
        exp.Delete,
        exp.Drop,
        exp.Insert,
        exp.LoadData,
        exp.Update,
    )
    if not isinstance(ast, exp.Select) or any(ast.find_all(*forbidden_types)):
        issues.append(DorisSqlIssue("NON_SELECT_SQL", "Generated AST must contain only a SELECT query."))
    if any(where.find(exp.Window) is not None for where in ast.find_all(exp.Where)):
        issues.append(
            DorisSqlIssue(
                "WINDOW_IN_WHERE",
                "Window functions must be materialized before filtering.",
            )
        )
    table_references = list(
        dict.fromkeys(
            table.name
            for table in ast.find_all(exp.Table)
            if table.name not in cte_names
        )
    )
    unknown = sorted(set(table_references) - allowed_tables)
    if unknown:
        issues.append(
            DorisSqlIssue(
                "UNKNOWN_TABLE_REFERENCE",
                "Generated query references unknown table(s): " + ", ".join(unknown),
            )
        )
    return DorisSqlValidationResult(
        passed=not issues,
        issues=issues,
        statement_count=1,
        table_references=table_references,
        contains_window=ast.find(exp.Window) is not None,
        contains_prefix_table=any(name.endswith("_prefix") for name in table_references),
    )
