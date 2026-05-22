from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .compiler import Compiler
from .executor import SQLiteSampleExecutor
from .reference import PandasReferenceEvaluator

ResultKey = Tuple[str, str]


@dataclass(frozen=True)
class EquivalenceResult:
    dsl: str
    passed: bool
    sql: str
    sql_keys: List[ResultKey]
    reference_keys: List[ResultKey]
    missing_keys: List[ResultKey]
    extra_keys: List[ResultKey]

    @property
    def sql_row_count(self) -> int:
        return len(self.sql_keys)

    @property
    def reference_row_count(self) -> int:
        return len(self.reference_keys)

    def to_markdown(self) -> str:
        lines = [
            "# SQL Equivalence Verification",
            "",
            f"- Passed: {self.passed}",
            f"- SQL rows: {self.sql_row_count}",
            f"- Reference rows: {self.reference_row_count}",
            f"- Missing keys: {len(self.missing_keys)}",
            f"- Extra keys: {len(self.extra_keys)}",
            "",
            "## DSL",
            "",
            "```text",
            self.dsl,
            "```",
            "",
            "## SQL",
            "",
            "```sql",
            self.sql,
            "```",
            "",
            "## Differences",
            "",
            "| Type | ts_code | trade_date |",
            "|---|---|---|",
        ]
        if not self.missing_keys and not self.extra_keys:
            lines.append("| none |  |  |")
        for ts_code, trade_date in self.missing_keys:
            lines.append(f"| missing | {ts_code} | {trade_date} |")
        for ts_code, trade_date in self.extra_keys:
            lines.append(f"| extra | {ts_code} | {trade_date} |")
        return "\n".join(lines)


def verify_sql_equivalence(dsl: str, data_dir: Path, compiler: Compiler = None) -> EquivalenceResult:
    compiler = compiler or Compiler()
    compiled = compiler.compile(dsl)
    sql_result = SQLiteSampleExecutor(data_dir, compiler.registry).execute(compiled.sql)
    reference_result = PandasReferenceEvaluator(data_dir).evaluate(dsl)

    sql_keys = sorted(sql_result.keys())
    reference_keys = sorted(reference_result.keys())
    sql_key_set = set(sql_keys)
    reference_key_set = set(reference_keys)
    missing = sorted(reference_key_set - sql_key_set)
    extra = sorted(sql_key_set - reference_key_set)
    return EquivalenceResult(
        dsl=dsl,
        passed=not missing and not extra,
        sql=compiled.sql,
        sql_keys=sql_keys,
        reference_keys=reference_keys,
        missing_keys=missing,
        extra_keys=extra,
    )
