from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "SQLiteSampleExecutor":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        if self._conn is None:
            self._conn = self._new_connection()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str) -> SqlExecutionResult:
        if self._conn is not None:
            return self._execute_on_connection(self._conn, sql)
        conn = self._new_connection()
        try:
            return self._execute_on_connection(conn, sql)
        finally:
            conn.close()

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        try:
            conn.row_factory = sqlite3.Row
            self._load_tables(conn)
            self._create_prefix_tables(conn)
            return conn
        except Exception:
            conn.close()
            raise

    def _execute_on_connection(self, conn: sqlite3.Connection, sql: str) -> SqlExecutionResult:
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
            _create_table_indexes(conn, physical_name, columns)

    def _create_prefix_tables(self, conn: sqlite3.Connection) -> None:
        groups = {}
        for indicator_meta in self.registry.indicators.values():
            if not indicator_meta.get("supports_prefix_sum"):
                continue
            key = (indicator_meta["table"], indicator_meta["prefix_table"])
            groups.setdefault(key, []).append(indicator_meta)

        for (source_logical, prefix_logical), indicators in groups.items():
            source_physical = self.registry.table(source_logical)["physical"]
            if not _table_exists(conn, source_physical):
                continue
            skeleton_physical = self.registry.table("daily_quote")["physical"]
            if not _table_exists(conn, skeleton_physical):
                continue
            prefix_meta = self.registry.table(prefix_logical)
            prefix_physical = prefix_meta["physical"]
            conn.execute(f"DROP TABLE IF EXISTS {_quote(prefix_physical)}")
            select_columns, from_sql, ts_expr, date_expr, value_alias = _prefix_select_context(
                source_logical,
                source_physical,
                skeleton_physical,
            )
            for meta in indicators:
                column = value_alias + "." + _quote(meta["column"]) if value_alias else _quote(meta["column"])
                prefix_column = _quote(meta["prefix_column"])
                select_columns.append(
                    "SUM("
                    + column
                    + f") OVER (PARTITION BY {ts_expr} ORDER BY {date_expr} "
                    + f"ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS {prefix_column}"
                )
            select_sql = ", ".join(select_columns)
            conn.execute(
                f"CREATE TABLE {_quote(prefix_physical)} AS "
                f"SELECT {select_sql} {from_sql}"
            )
            _create_table_indexes(conn, prefix_physical, ["ts_code", "trade_date", "row_no"])


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


def _prefix_select_context(
    source_logical: str,
    source_physical: str,
    skeleton_physical: str,
) -> tuple[List[str], str, str, str, str]:
    if source_logical == "daily_quote":
        ts_expr = _quote("ts_code")
        date_expr = _quote("trade_date")
        return (
            [
                ts_expr,
                date_expr,
                f"ROW_NUMBER() OVER (PARTITION BY {ts_expr} ORDER BY {date_expr}) AS {_quote('row_no')}",
            ],
            f"FROM {_quote(source_physical)}",
            ts_expr,
            date_expr,
            "",
        )

    skeleton_alias = _quote("__skel")
    source_alias = _quote("__src")
    ts_expr = skeleton_alias + "." + _quote("ts_code")
    date_expr = skeleton_alias + "." + _quote("trade_date")
    from_sql = (
        f"FROM {_quote(skeleton_physical)} AS {skeleton_alias} "
        f"LEFT JOIN {_quote(source_physical)} AS {source_alias} "
        f"ON {source_alias}.{_quote('ts_code')} = {ts_expr} "
        f"AND {source_alias}.{_quote('trade_date')} = {date_expr}"
    )
    return (
        [
            f"{ts_expr} AS {_quote('ts_code')}",
            f"{date_expr} AS {_quote('trade_date')}",
            f"ROW_NUMBER() OVER (PARTITION BY {ts_expr} ORDER BY {date_expr}) AS {_quote('row_no')}",
        ],
        from_sql,
        ts_expr,
        date_expr,
        source_alias,
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _create_table_indexes(conn: sqlite3.Connection, table_name: str, columns: List[str]) -> None:
    if {"ts_code", "trade_date"}.issubset(columns):
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote(_index_name(table_name, 'code_date'))} "
            f"ON {_quote(table_name)} (ts_code, trade_date)"
        )
    if {"ts_code", "row_no"}.issubset(columns):
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote(_index_name(table_name, 'code_row'))} "
            f"ON {_quote(table_name)} (ts_code, row_no)"
        )


def _index_name(table_name: str, suffix: str) -> str:
    return "idx_" + "".join(char if char.isalnum() else "_" for char in table_name) + "_" + suffix
