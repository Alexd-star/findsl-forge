from __future__ import annotations

import json
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence

from .compiler import Compiler
from .evaluation import _percentile


DEFAULT_DORIS_EVIDENCE_DSL = 'filter(SUM(indicator("volume"), 120) > 420000)'


@dataclass(frozen=True)
class DorisClientConfig:
    host: str
    port: int
    user: str
    database: str
    password: str = ""
    client: str = "mysql"
    connect_timeout_seconds: int = 10

    def command(self, sql: str, password_mode: str = "none") -> List[str]:
        _validate_password_mode(self, password_mode)
        auth_args = ["-u", self.user]
        if password_mode == "inline" and self.password:
            auth_args.append(f"-p{self.password}")
        elif password_mode == "prompt":
            auth_args.append("-p")

        return [
            self.client,
            "-h",
            self.host,
            "-P",
            str(self.port),
            *auth_args,
            "--connect-timeout",
            str(self.connect_timeout_seconds),
            "--init-command",
            "SET enable_sql_cache=false",
            "--batch",
            "--raw",
            "--skip-column-names",
            self.database,
            "-e",
            sql,
        ]


@dataclass(frozen=True)
class DorisVariantEvidence:
    name: str
    sql: str
    explain_text: str
    execute_ms: List[float]
    row_count: int
    success: bool
    error: str = ""

    @property
    def avg_execute_ms(self) -> float:
        return mean(self.execute_ms) if self.execute_ms else 0.0

    @property
    def p95_execute_ms(self) -> float:
        return _percentile(self.execute_ms, 95) if self.execute_ms else 0.0

    @property
    def plan_contains_prefix(self) -> bool:
        return "_prefix" in self.explain_text or "_prefix" in self.sql

    @property
    def plan_contains_window(self) -> bool:
        return "WINDOW" in self.explain_text.upper() or "ROWS BETWEEN" in self.sql.upper()


@dataclass(frozen=True)
class DorisEvidenceResult:
    dsl: str
    database: str
    iterations: int
    min_speedup: float
    baseline: DorisVariantEvidence
    optimized: DorisVariantEvidence
    generated_at: str
    client_command: str
    git_head: str = "unavailable"

    @property
    def passed(self) -> bool:
        return (
            self.baseline.success
            and self.optimized.success
            and self.row_counts_match
            and self.baseline.plan_contains_window
            and self.optimized.plan_contains_prefix
            and self.speedup_target_met
        )

    @property
    def row_counts_match(self) -> bool:
        return self.baseline.row_count == self.optimized.row_count

    @property
    def speedup(self) -> float:
        if self.optimized.avg_execute_ms <= 0:
            return 0.0
        return self.baseline.avg_execute_ms / self.optimized.avg_execute_ms

    @property
    def speedup_target_met(self) -> bool:
        return self.speedup >= self.min_speedup

    def to_dict(self) -> Dict[str, object]:
        return {
            "dsl": self.dsl,
            "database": self.database,
            "iterations": self.iterations,
            "min_speedup": self.min_speedup,
            "generated_at": self.generated_at,
            "client_command": self.client_command,
            "git_head": self.git_head,
            "passed": self.passed,
            "row_counts_match": self.row_counts_match,
            "speedup": self.speedup,
            "speedup_target_met": self.speedup_target_met,
            "baseline_plan_contains_window": self.baseline.plan_contains_window,
            "optimized_plan_contains_prefix": self.optimized.plan_contains_prefix,
            "baseline": _variant_to_dict(self.baseline),
            "optimized": _variant_to_dict(self.optimized),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Doris Cluster Evidence",
            "",
            "## Summary",
            "",
            "- Evidence source: Apache Doris MySQL-compatible query port",
            f"- Generated at: {self.generated_at}",
            f"- Git HEAD: `{self.git_head}`",
            f"- Database: `{self.database}`",
            f"- Iterations: {self.iterations}",
            f"- Client command template: `{self.client_command}`",
            f"- Evidence passed: {self.passed}",
            f"- Baseline success: {self.baseline.success}",
            f"- Optimized success: {self.optimized.success}",
            f"- Row counts match: {self.row_counts_match}",
            f"- Baseline row count: {self.baseline.row_count}",
            f"- Optimized row count: {self.optimized.row_count}",
            f"- Doris cluster speedup: {self.speedup:.2f}x",
            f"- Minimum Doris speedup target: {self.min_speedup:.2f}x",
            f"- Doris speedup target met: {self.speedup_target_met}",
            f"- Baseline avg execute ms: {self.baseline.avg_execute_ms:.3f}",
            f"- Optimized avg execute ms: {self.optimized.avg_execute_ms:.3f}",
            f"- Baseline P95 execute ms: {self.baseline.p95_execute_ms:.3f}",
            f"- Optimized P95 execute ms: {self.optimized.p95_execute_ms:.3f}",
            f"- Optimized plan contains prefix table: {self.optimized.plan_contains_prefix}",
            f"- Baseline plan contains window: {self.baseline.plan_contains_window}",
            "",
            "This is the Doris-scale evidence file consumed by the final evidence pipeline.",
            "Only generate it after loading schema, sample or scale data, and prefix tables into a real Doris cluster.",
            "",
            "## DSL",
            "",
            "```text",
            self.dsl,
            "```",
            "",
            "## Variant Metrics",
            "",
            "| Variant | Success | Avg execute ms | P95 execute ms | Rows | Prefix plan | Window plan |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for variant in [self.baseline, self.optimized]:
            lines.append(
                f"| {variant.name} | {variant.success} | {variant.avg_execute_ms:.3f} | "
                f"{variant.p95_execute_ms:.3f} | {variant.row_count} | "
                f"{variant.plan_contains_prefix} | {variant.plan_contains_window} |"
            )
        lines.extend(["", "## EXPLAIN Output", ""])
        for variant in [self.baseline, self.optimized]:
            lines.extend(
                [
                    f"### {variant.name}",
                    "",
                    "```text",
                    variant.explain_text or variant.error or "<empty>",
                    "```",
                    "",
                    "SQL:",
                    "",
                    "```sql",
                    variant.sql,
                    "```",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


def collect_doris_evidence(
    config: DorisClientConfig,
    output_path: Path,
    dsl: str = DEFAULT_DORIS_EVIDENCE_DSL,
    iterations: int = 3,
    password_mode: str = "none",
    min_speedup: float = 10.0,
) -> DorisEvidenceResult:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if min_speedup < 0:
        raise ValueError("min_speedup must be non-negative")
    _validate_password_mode(config, password_mode)
    compiler = Compiler()
    baseline = compiler.compile(dsl, enable_prefix_sum=False)
    optimized = compiler.compile(dsl, enable_prefix_sum=True)
    result = DorisEvidenceResult(
        dsl=dsl,
        database=config.database,
        iterations=iterations,
        min_speedup=min_speedup,
        baseline=_collect_variant(config, "baseline_window", baseline.sql, iterations, password_mode),
        optimized=_collect_variant(config, "optimized_prefix_sum", optimized.sql, iterations, password_mode),
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        client_command=_redacted_command(config.command("SELECT 1", password_mode=password_mode)),
        git_head=_git_head(),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    (output_path.with_suffix(".json")).write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _collect_variant(
    config: DorisClientConfig,
    name: str,
    sql: str,
    iterations: int,
    password_mode: str,
) -> DorisVariantEvidence:
    try:
        explain = _run_sql(config, "EXPLAIN " + sql, password_mode)
        execute_ms = []
        row_count = 0
        count_sql = f"SELECT COUNT(*) FROM ({sql}) evidence_query"
        for _ in range(iterations):
            started = time.perf_counter()
            output = _run_sql(config, count_sql, password_mode)
            execute_ms.append((time.perf_counter() - started) * 1000)
            row_count = _parse_count(output)
        return DorisVariantEvidence(
            name=name,
            sql=sql,
            explain_text=explain.strip(),
            execute_ms=execute_ms,
            row_count=row_count,
            success=True,
        )
    except Exception as exc:  # noqa: BLE001 - evidence report must preserve cluster failures.
        return DorisVariantEvidence(
            name=name,
            sql=sql,
            explain_text="",
            execute_ms=[],
            row_count=0,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def _run_sql(config: DorisClientConfig, sql: str, password_mode: str) -> str:
    completed = subprocess.run(
        config.command(sql, password_mode=password_mode),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Doris client failed with exit "
            f"{completed.returncode}: {(completed.stderr or completed.stdout).strip()}"
        )
    return completed.stdout


def _parse_count(output: str) -> int:
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            return int(stripped.split()[0])
        except (ValueError, IndexError):
            continue
    raise ValueError(f"Could not parse COUNT(*) output: {output!r}")


def _variant_to_dict(variant: DorisVariantEvidence) -> Dict[str, object]:
    return {
        "name": variant.name,
        "success": variant.success,
        "avg_execute_ms": variant.avg_execute_ms,
        "p95_execute_ms": variant.p95_execute_ms,
        "row_count": variant.row_count,
        "plan_contains_prefix": variant.plan_contains_prefix,
        "plan_contains_window": variant.plan_contains_window,
        "error": variant.error,
        "sql": variant.sql,
        "explain_text": variant.explain_text,
    }


def _redacted_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part if not part.startswith("-p") or part == "-p" else "-p***") for part in command)


def _validate_password_mode(config: DorisClientConfig, password_mode: str) -> None:
    if password_mode not in {"none", "inline", "prompt"}:
        raise ValueError(f"unsupported password_mode: {password_mode}")
    if config.password and password_mode == "none":
        raise ValueError("password was provided but password_mode is none")
