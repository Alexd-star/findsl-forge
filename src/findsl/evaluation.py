from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List

from .compiler import Compiler


@dataclass(frozen=True)
class CaseResult:
    name: str
    dsl: str
    passed: bool
    elapsed_ms: float
    sql: str
    trace: List[str]
    errors: List[str]


@dataclass(frozen=True)
class EvaluationResult:
    total: int
    passed: int
    failed: int
    compile_success_rate: float
    fragment_accuracy: float
    avg_elapsed_ms: float
    p50_elapsed_ms: float
    p95_elapsed_ms: float
    cases: List[CaseResult]

    def to_markdown(self) -> str:
        lines = [
            "# FinDSL Forge Evaluation Report",
            "",
            "## Summary",
            "",
            f"- Total cases: {self.total}",
            f"- Passed cases: {self.passed}",
            f"- Failed cases: {self.failed}",
            f"- Compile success rate: {self.compile_success_rate:.2%}",
            f"- Fragment accuracy: {self.fragment_accuracy:.2%}",
            f"- Average compile latency: {self.avg_elapsed_ms:.3f} ms",
            f"- P50 compile latency: {self.p50_elapsed_ms:.3f} ms",
            f"- P95 compile latency: {self.p95_elapsed_ms:.3f} ms",
            "",
            "## Case Details",
            "",
            "| Case | Passed | Latency ms | Errors |",
            "|---|---:|---:|---|",
        ]
        for case in self.cases:
            errors = "<br>".join(case.errors) if case.errors else ""
            lines.append(f"| {case.name} | {case.passed} | {case.elapsed_ms:.3f} | {errors} |")
        lines.extend(["", "## Generated SQL", ""])
        for case in self.cases:
            lines.extend(
                [
                    f"### {case.name}",
                    "",
                    "```sql",
                    case.sql,
                    "```",
                    "",
                    "Trace:",
                ]
            )
            lines.extend(f"- {item}" for item in case.trace)
            lines.append("")
        return "\n".join(lines)


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return cases


def evaluate(cases: Iterable[Dict[str, Any]], compiler: Compiler = None) -> EvaluationResult:
    compiler = compiler or Compiler()
    results: List[CaseResult] = []
    expected_checks = 0
    passed_checks = 0
    compile_success = 0
    for case in cases:
        errors: List[str] = []
        sql = ""
        trace: List[str] = []
        elapsed_ms = 0.0
        try:
            compiled = compiler.compile(case["dsl"])
            compile_success += 1
            sql = compiled.sql
            trace = compiled.trace
            elapsed_ms = compiled.elapsed_ms
            trace_blob = "\n".join(trace)
            for fragment in case.get("expected_sql_fragments", []):
                expected_checks += 1
                if fragment in sql:
                    passed_checks += 1
                else:
                    errors.append(f"missing SQL fragment: {fragment}")
            for fragment in case.get("expected_trace_fragments", []):
                expected_checks += 1
                if fragment in trace_blob:
                    passed_checks += 1
                else:
                    errors.append(f"missing trace fragment: {fragment}")
        except Exception as exc:  # noqa: BLE001 - report all compiler failures in evaluation output.
            errors.append(f"compile error: {type(exc).__name__}: {exc}")
        results.append(
            CaseResult(
                name=case.get("name", "<unnamed>"),
                dsl=case.get("dsl", ""),
                passed=not errors,
                elapsed_ms=elapsed_ms,
                sql=sql,
                trace=trace,
                errors=errors,
            )
        )
    latencies = [case.elapsed_ms for case in results if case.elapsed_ms > 0]
    total = len(results)
    passed = sum(1 for case in results if case.passed)
    return EvaluationResult(
        total=total,
        passed=passed,
        failed=total - passed,
        compile_success_rate=compile_success / total if total else 0.0,
        fragment_accuracy=passed_checks / expected_checks if expected_checks else 1.0,
        avg_elapsed_ms=mean(latencies) if latencies else 0.0,
        p50_elapsed_ms=median(latencies) if latencies else 0.0,
        p95_elapsed_ms=_percentile(latencies, 95) if latencies else 0.0,
        cases=results,
    )


def evaluate_file(input_path: Path, output_path: Path = None) -> EvaluationResult:
    result = evaluate(load_cases(input_path))
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight

