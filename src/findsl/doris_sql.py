from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Set

from .registry import Registry, default_registry


@dataclass(frozen=True)
class DorisSqlIssue:
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class DorisSqlValidationResult:
    passed: bool
    issues: List[DorisSqlIssue]
    statement_count: int
    table_references: List[str]
    contains_window: bool
    contains_prefix_table: bool

    def to_explain_evidence(self) -> Dict[str, object]:
        return {
            "issue_count": len(self.issues),
            "statement_count": self.statement_count,
            "table_references": list(self.table_references),
            "contains_window": self.contains_window,
            "contains_prefix_table": self.contains_prefix_table,
        }


FORBIDDEN_STATEMENT_TOKENS = {
    "ALTER",
    "CALL",
    "CREATE",
    "DELETE",
    "DROP",
    "EXEC",
    "INSERT",
    "LOAD",
    "TRUNCATE",
    "UPDATE",
}


def validate_doris_select_sql(sql: str, registry: Registry = None) -> DorisSqlValidationResult:
    registry = registry or default_registry()
    masked, scan_issues, semicolon_count = _mask_string_literals(sql)
    issues = list(scan_issues)
    statement_count = 0 if not sql.strip() else semicolon_count + 1
    upper = masked.upper()

    if not upper.lstrip().startswith(("SELECT", "WITH")):
        issues.append(DorisSqlIssue("NON_SELECT_SQL", "Generated SQL must be a SELECT or WITH query."))
    if semicolon_count:
        issues.append(DorisSqlIssue("MULTI_STATEMENT_SQL", "Generated SQL must not contain statement separators."))
    if not _parentheses_balanced(masked):
        issues.append(DorisSqlIssue("UNBALANCED_PARENTHESES", "Generated SQL has unbalanced parentheses."))
    if _contains_comment_marker(masked):
        issues.append(DorisSqlIssue("SQL_COMMENT_MARKER", "Generated SQL must not contain SQL comments outside literals."))

    forbidden = sorted(token for token in FORBIDDEN_STATEMENT_TOKENS if _contains_word(upper, token))
    if forbidden:
        issues.append(
            DorisSqlIssue(
                "FORBIDDEN_STATEMENT_TOKEN",
                "Generated query contains forbidden statement token(s): " + ", ".join(forbidden),
            )
        )
    if _where_contains_window(upper):
        issues.append(
            DorisSqlIssue(
                "WINDOW_IN_WHERE",
                "Window functions must be materialized before filtering, not emitted directly inside WHERE.",
            )
        )

    table_references = _table_references(masked)
    allowed_tables = _allowed_table_references(registry)
    unknown_tables = [name for name in table_references if name not in allowed_tables and not re.fullmatch(r"stage\d+", name)]
    if unknown_tables:
        issues.append(
            DorisSqlIssue(
                "UNKNOWN_TABLE_REFERENCE",
                "Generated query references unknown table(s): " + ", ".join(sorted(set(unknown_tables))),
            )
        )

    return DorisSqlValidationResult(
        passed=not issues,
        issues=issues,
        statement_count=statement_count,
        table_references=table_references,
        contains_window=" OVER " in upper or " OVER(" in upper,
        contains_prefix_table=any(name.endswith("_prefix") for name in table_references),
    )


def _mask_string_literals(sql: str) -> tuple[str, List[DorisSqlIssue], int]:
    chars: List[str] = []
    issues: List[DorisSqlIssue] = []
    semicolon_count = 0
    i = 0
    in_string = False
    while i < len(sql):
        ch = sql[i]
        if in_string:
            if ch == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    chars.extend([" ", " "])
                    i += 2
                    continue
                in_string = False
            chars.append(" ")
            i += 1
            continue
        if ch == "'":
            in_string = True
            chars.append(" ")
            i += 1
            continue
        if ch == ";":
            semicolon_count += 1
        chars.append(ch)
        i += 1
    if in_string:
        issues.append(DorisSqlIssue("UNCLOSED_STRING_LITERAL", "Generated SQL has an unclosed string literal."))
    return "".join(chars), issues, semicolon_count


def _parentheses_balanced(sql: str) -> bool:
    depth = 0
    for ch in sql:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _contains_comment_marker(sql: str) -> bool:
    return "--" in sql or "/*" in sql or "*/" in sql


def _contains_word(upper_sql: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", upper_sql) is not None


def _where_contains_window(upper_sql: str) -> bool:
    for match in re.finditer(r"\bWHERE\b", upper_sql):
        segment = _where_expression_segment(upper_sql, match.end(), _depth_at(upper_sql, match.start()))
        if re.search(r"\bOVER\s*\(", segment):
            return True
    return False


def _where_expression_segment(upper_sql: str, start: int, start_depth: int) -> str:
    depth = start_depth
    idx = start
    while idx < len(upper_sql):
        ch = upper_sql[idx]
        if depth == start_depth and _starts_clause_boundary(upper_sql, idx):
            break
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth <= start_depth:
                break
            depth -= 1
        idx += 1
    return upper_sql[start:idx]


def _depth_at(sql: str, offset: int) -> int:
    depth = 0
    for ch in sql[:offset]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    return depth


def _starts_clause_boundary(upper_sql: str, idx: int) -> bool:
    boundaries = (" GROUP BY ", " HAVING ", " ORDER BY ", " LIMIT ", " UNION ")
    return any(upper_sql.startswith(boundary, idx) for boundary in boundaries)


def _table_references(sql: str) -> List[str]:
    names = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\b", sql, flags=re.IGNORECASE)
    return list(dict.fromkeys(names))


def _allowed_table_references(registry: Registry) -> Set[str]:
    return {str(meta["physical"]) for meta in registry.tables.values()}
