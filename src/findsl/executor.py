from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .registry import Registry, default_registry


@dataclass(frozen=True)
class SqlExecutionResult:
    sql: str
    rows: List[Dict[str, Any]]

    def keys(self):
        return [(str(row["ts_code"]), str(row["trade_date"])) for row in self.rows]


class SQLiteSampleExecutor:
    """Execute generated SQL against local CSV fixtures loaded into SQLite."""

    def __init__(self, data_dir: Path, registry: Registry = None):
        self.data_dir = Path(data_dir)
        self.registry = registry or default_registry()

    def execute(self, sql: str) -> SqlExecutionResult:
        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            self._load_tables(conn)
            rows = [dict(row) for row in conn.execute(sql).fetchall()]
        rows.sort(key=lambda row: (str(row.get("trade_date", "")), str(row.get("ts_code", ""))))
        return SqlExecutionResult(sql=sql, rows=rows)

    def _load_tables(self, conn: sqlite3.Connection) -> None:
        for logical_name, meta in self.registry.tables.items():
            csv_path = self.data_dir / f"{logical_name}.csv"
            if not csv_path.exists():
                continue
            rows = _read_csv(csv_path)
            if not rows:
                continue
            physical_name = meta["physical"]
            columns = list(rows[0].keys())
            schema = ", ".join(f"{_quote(column)} {_sqlite_type(column, rows)}" for column in columns)
            conn.execute(f"CREATE TABLE {_quote(physical_name)} ({schema})")
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(_quote(column) for column in columns)
            values = [[_coerce(row[column]) for column in columns] for row in rows]
            conn.executemany(
                f"INSERT INTO {_quote(physical_name)} ({column_sql}) VALUES ({placeholders})",
                values,
            )


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _sqlite_type(column: str, rows: Iterable[Dict[str, str]]) -> str:
    if column in {"ts_code", "trade_date", "market"}:
        return "TEXT"
    values = [row[column] for row in rows if row.get(column) not in {None, ""}]
    if values and all(_is_int(value) for value in values):
        return "INTEGER"
    if values and all(_is_number(value) for value in values):
        return "REAL"
    return "TEXT"


def _coerce(value: str):
    if value == "":
        return None
    if _is_int(value):
        return int(value)
    if _is_number(value):
        return float(value)
    return value


def _is_int(value: str) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def _is_number(value: str) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
