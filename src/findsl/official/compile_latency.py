from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

from .context import CompileContext, default_compile_context
from .performance import PerformanceCase
from .pipeline import compile_official


class CompileLatencyContractError(ValueError):
    pass


def run_compile_latency_benchmark(
    cases: Iterable[PerformanceCase],
    *,
    context: CompileContext | None = None,
    compiler: Callable[..., Any] = compile_official,
    warmups: int = 1,
    repeats: int = 30,
    target_p95_ms: float = 50.0,
) -> Dict[str, Any]:
    case_list = tuple(cases)
    if not case_list:
        raise CompileLatencyContractError("compile latency benchmark is empty")
    if warmups < 0 or repeats < 3 or target_p95_ms <= 0:
        raise CompileLatencyContractError("invalid compile latency benchmark settings")
    compile_context = context or default_compile_context()
    results = []
    all_latencies = []
    all_stage_latencies: Dict[str, list[float]] = {}
    for case in case_list:
        error = ""
        selected_strategy = ""
        case_latencies = []
        case_stage_latencies: Dict[str, list[float]] = {}
        try:
            for _ in range(warmups):
                compiler(case.dsl, context=compile_context)
            for _ in range(repeats):
                compiled = compiler(case.dsl, context=compile_context)
                case_latencies.append(float(compiled.elapsed_ms))
                selected_strategy = str(compiled.physical["selected_strategy"])
                for stage, elapsed_ns in compiled.timings_ns.items():
                    elapsed_ms = float(elapsed_ns) / 1_000_000.0
                    case_stage_latencies.setdefault(stage, []).append(elapsed_ms)
                    all_stage_latencies.setdefault(stage, []).append(elapsed_ms)
        except Exception as exc:  # noqa: BLE001 - every case remains visible in the report.
            error = f"{type(exc).__name__}: {exc}"
        all_latencies.extend(case_latencies)
        results.append(
            {
                "case_id": case.case_id,
                "function_families": list(case.function_families),
                "plan_family": case.plan_family,
                "selected_strategy": selected_strategy,
                "sample_count": len(case_latencies),
                "p50_ms": _percentile(case_latencies, 0.50),
                "p95_ms": _percentile(case_latencies, 0.95),
                "p99_ms": _percentile(case_latencies, 0.99),
                "max_ms": max(case_latencies, default=None),
                "stage_p95_ms": {
                    stage: _percentile(values, 0.95)
                    for stage, values in sorted(case_stage_latencies.items())
                },
                "status": "PASS" if not error else "ERROR",
                "error": error,
            }
        )
    errors = [item for item in results if item["status"] != "PASS"]
    p95_ms = _percentile(all_latencies, 0.95)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(),
        "catalog_snapshot_id": compile_context.context_id,
        "case_count": len(case_list),
        "sample_count": len(all_latencies),
        "warmups": warmups,
        "repeats": repeats,
        "target_p95_ms": target_p95_ms,
        "p50_ms": _percentile(all_latencies, 0.50),
        "p95_ms": p95_ms,
        "p99_ms": _percentile(all_latencies, 0.99),
        "max_ms": max(all_latencies, default=None),
        "mean_ms": round(sum(all_latencies) / len(all_latencies), 6)
        if all_latencies
        else None,
        "stage_p95_ms": {
            stage: _percentile(values, 0.95)
            for stage, values in sorted(all_stage_latencies.items())
        },
        "function_families": sorted(
            {family for case in case_list for family in case.function_families}
        ),
        "plan_families": sorted({case.plan_family for case in case_list}),
        "failed_cases": len(errors),
        "target_met": not errors and p95_ms is not None and p95_ms < target_p95_ms,
        "results": results,
    }


def write_compile_latency_report(
    report: Mapping[str, Any],
    json_path: Path,
    markdown_path: Path,
) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# 正式编译器延迟基准",
        "",
        f"- Git HEAD：`{report.get('git_head')}`",
        f"- Catalog snapshot：`{report.get('catalog_snapshot_id')}`",
        f"- 用例/样本：`{report.get('case_count')}/{report.get('sample_count')}`",
        f"- P50/P95/P99：`{report.get('p50_ms')}/{report.get('p95_ms')}/{report.get('p99_ms')}` ms",
        f"- P95 目标：`<{report.get('target_p95_ms')}` ms",
        f"- 门禁：`{'PASS' if report.get('target_met') else 'FAIL'}`",
        "",
        "| Case | 函数族 | 计划族 | 策略 | P50 | P95 | P99 | Max | 状态 |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report.get("results") or []:
        lines.append(
            f"| {item['case_id']} | {','.join(item['function_families'])} | "
            f"{item['plan_family']} | {item['selected_strategy']} | "
            f"{item['p50_ms']} | {item['p95_ms']} | {item['p99_ms']} | "
            f"{item['max_ms']} | {item['status']} |"
        )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return round(ordered[index], 6)


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"
