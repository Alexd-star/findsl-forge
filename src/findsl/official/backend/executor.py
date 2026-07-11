from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Tuple

import sqlglot
from sqlglot import exp

from .diff import hash_result_rows


class DorisExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class DorisExecutionConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    mysql_executable: str = "mysql"
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class DorisExecutionResult:
    rows: Tuple[Tuple[str, ...], ...]
    elapsed_ms: float
    ordered_hash: str
    unordered_hash: str


def execute_doris_query(
    config: DorisExecutionConfig,
    sql: str,
    *,
    runner: Callable = subprocess.run,
) -> DorisExecutionResult:
    statements = sqlglot.parse(sql, read="doris")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise DorisExecutionError("only one Doris SELECT statement may be executed")

    command = [
        config.mysql_executable,
        "--batch",
        "--raw",
        "--skip-column-names",
        "--host", config.host,
        "--port", str(config.port),
        "--user", config.user,
        "--database", config.database,
        "--execute", sql,
    ]
    environment = os.environ.copy()
    if config.password:
        environment["MYSQL_PWD"] = config.password
    started = perf_counter()
    completed = runner(
        command,
        env=environment,
        text=True,
        capture_output=True,
        timeout=config.timeout_seconds,
        check=False,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    if completed.returncode != 0:
        detail = (completed.stderr or "Doris client failed").strip()
        if config.password:
            detail = detail.replace(config.password, "<redacted>")
        raise DorisExecutionError(f"Doris client exited with {completed.returncode}: {detail}")
    rows = tuple(
        tuple(cell for cell in line.split("\t"))
        for line in completed.stdout.splitlines()
        if line
    )
    return DorisExecutionResult(
        rows=rows,
        elapsed_ms=elapsed_ms,
        ordered_hash=hash_result_rows(rows, ordered=True),
        unordered_hash=hash_result_rows(rows, ordered=False),
    )
