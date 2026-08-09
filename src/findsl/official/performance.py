from __future__ import annotations

import json
import hashlib
import math
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable, Dict, Iterable, Mapping, Tuple

from .backend.executor import (
    DorisExecutionConfig,
    execute_doris_explain,
    execute_doris_query,
)
from .context import CompileContext, default_compile_context
from .correctness import CorrectnessCase
from .pipeline import compile_official


class PerformanceContractError(ValueError):
    pass


@dataclass(frozen=True)
class PerformanceCase:
    case_id: str
    dsl: str
    function_families: Tuple[str, ...]
    plan_family: str
    load_tier: str
    reference_sql_path: str
    expected_non_empty: bool


@dataclass(frozen=True)
class PerformanceCaseResult:
    case_id: str
    status: str
    matched_reference: bool
    function_families: Tuple[str, ...]
    plan_family: str
    selected_strategy: str
    load_tier: str
    row_count: int
    compile_ms: float
    execute_p50_ms: float
    execute_p95_ms: float
    execute_p99_ms: float
    execute_max_ms: float
    under_10s: bool
    explain_sha256: str
    error: str = ""


def select_performance_cases(
    correctness_cases: Iterable[CorrectnessCase],
    *,
    per_family: int = 3,
    max_cases: int = 48,
) -> Tuple[PerformanceCase, ...]:
    eligible = sorted(
        (case for case in correctness_cases if case.score_eligible),
        key=lambda item: item.case_id,
    )
    if per_family <= 0 or max_cases <= 0:
        raise PerformanceContractError("performance case limits must be positive")
    selected: Dict[str, CorrectnessCase] = {}
    families = sorted({family for case in eligible for family in case.function_families})
    for family in families:
        candidates = [case for case in eligible if family in case.function_families]
        candidates.sort(
            key=lambda item: (
                sum(
                    1
                    for existing in selected.values()
                    if existing.plan_family == item.plan_family
                ),
                not item.expected_non_empty,
                item.case_id,
            )
        )
        for case in candidates[:per_family]:
            selected.setdefault(case.case_id, case)
    plan_families = sorted({case.plan_family for case in eligible})
    for plan_family in plan_families:
        if len(selected) >= max_cases:
            break
        if any(case.plan_family == plan_family for case in selected.values()):
            continue
        case = next(item for item in eligible if item.plan_family == plan_family)
        selected[case.case_id] = case
    if len(selected) < max_cases:
        for case in eligible:
            if len(selected) >= max_cases:
                break
            selected.setdefault(case.case_id, case)
    return tuple(
        PerformanceCase(
            case.case_id,
            case.dsl,
            case.function_families,
            case.plan_family,
            _load_tier(case),
            case.reference_sql_path,
            case.expected_non_empty,
        )
        for case in sorted(selected.values(), key=lambda item: item.case_id)[:max_cases]
    )


def load_performance_manifest(path: Path) -> Tuple[PerformanceCase, ...]:
    cases = []
    seen = set()
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        raw = json.loads(line)
        expected = {
            "case_id",
            "dsl",
            "function_families",
            "plan_family",
            "load_tier",
            "reference_sql_path",
            "expected_non_empty",
        }
        if not isinstance(raw, Mapping) or set(raw) != expected:
            raise PerformanceContractError(
                f"invalid performance case at line {line_number}"
            )
        case = PerformanceCase(
            str(raw["case_id"]),
            str(raw["dsl"]),
            tuple(sorted({str(item) for item in raw["function_families"]})),
            str(raw["plan_family"]),
            str(raw["load_tier"]),
            str(raw["reference_sql_path"]),
            bool(raw["expected_non_empty"]),
        )
        if case.case_id in seen:
            raise PerformanceContractError(f"duplicate performance case: {case.case_id}")
        if case.load_tier not in {"light", "medium", "heavy"}:
            raise PerformanceContractError(f"invalid load tier: {case.case_id}")
        if not case.function_families:
            raise PerformanceContractError(f"missing function family: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise PerformanceContractError("performance manifest is empty")
    return tuple(cases)


def write_performance_manifest(cases: Iterable[PerformanceCase], path: Path) -> None:
    case_list = tuple(cases)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "\n".join(
            json.dumps(asdict(case), ensure_ascii=False, sort_keys=True)
            for case in case_list
        )
        + "\n",
        encoding="utf-8",
    )


def run_performance_matrix(
    cases: Iterable[PerformanceCase],
    *,
    manifest_root: Path,
    doris: DorisExecutionConfig,
    warmups: int = 1,
    repeats: int = 7,
    context: CompileContext | None = None,
    compiler: Callable[..., Any] = compile_official,
    executor: Callable = execute_doris_query,
    explainer: Callable = execute_doris_explain,
) -> Dict[str, Any]:
    if warmups < 0 or repeats < 3:
        raise PerformanceContractError("warmups must be non-negative and repeats at least 3")
    compile_context = context or default_compile_context()
    results = []
    for case in cases:
        results.append(
            _run_case(
                case,
                manifest_root=manifest_root,
                doris=doris,
                warmups=warmups,
                repeats=repeats,
                context=compile_context,
                compiler=compiler,
                executor=executor,
                explainer=explainer,
            )
        )
    successful = [item for item in results if item.status == "PASS"]
    all_under_10s = bool(results) and all(
        item.status == "PASS" and item.under_10s for item in results
    )
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(),
        "catalog_snapshot_id": compile_context.context_id,
        "case_count": len(results),
        "passed": len(successful),
        "failed": len(results) - len(successful),
        "all_matched_reference": bool(results)
        and all(item.matched_reference for item in results),
        "all_queries_under_10s": all_under_10s,
        "max_p95_ms": max((item.execute_p95_ms for item in successful), default=None),
        "warmups": warmups,
        "repeats": repeats,
        "groups": _groups(results),
        "results": [asdict(item) for item in results],
    }


def write_performance_report(report: Mapping[str, Any], json_path: Path, markdown_path: Path) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# 官方真实数据分层性能矩阵",
        "",
        f"- Git HEAD：`{report.get('git_head')}`",
        f"- Catalog snapshot：`{report.get('catalog_snapshot_id')}`",
        f"- 用例：`{report.get('case_count')}`",
        f"- 全部匹配独立 reference：`{report.get('all_matched_reference')}`",
        f"- 全部 P95 <= 10s：`{report.get('all_queries_under_10s')}`",
        f"- 最大 P95：`{report.get('max_p95_ms')}` ms",
        "",
        "| Case | 函数族 | 计划族 | 策略 | 负载 | Rows | Compile ms | P95 ms | 10s | 状态 |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for item in report.get("results") or []:
        lines.append(
            f"| {item['case_id']} | {','.join(item['function_families'])} | "
            f"{item['plan_family']} | {item['selected_strategy']} | {item['load_tier']} | "
            f"{item['row_count']} | {item['compile_ms']} | {item['execute_p95_ms']} | "
            f"{item['under_10s']} | {item['status']} |"
        )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_case(
    case,
    *,
    manifest_root,
    doris,
    warmups,
    repeats,
    context,
    compiler,
    executor,
    explainer,
):
    try:
        compiled = compiler(case.dsl, context=context)
        reference_sql = (Path(manifest_root) / case.reference_sql_path).read_text(
            encoding="utf-8"
        )
        reference = executor(doris, reference_sql)
        if case.expected_non_empty and not reference.rows:
            raise PerformanceContractError("reference result is unexpectedly empty")
        for _ in range(warmups):
            executor(doris, compiled.backend["sql"])
        runs = tuple(executor(doris, compiled.backend["sql"]) for _ in range(repeats))
        matched = all(
            len(run.rows) == len(reference.rows)
            and run.unordered_hash == reference.unordered_hash
            for run in runs
        )
        if not matched:
            raise PerformanceContractError("generated result differs from independent reference")
        timings = sorted(run.elapsed_ms for run in runs)
        explain = explainer(doris, compiled.backend["sql"])
        p95 = _percentile(timings, 0.95)
        return PerformanceCaseResult(
            case.case_id,
            "PASS" if p95 <= 10_000 else "FAIL",
            True,
            case.function_families,
            case.plan_family,
            compiled.physical["selected_strategy"],
            case.load_tier,
            len(reference.rows),
            compiled.elapsed_ms,
            median(timings),
            p95,
            _percentile(timings, 0.99),
            timings[-1],
            p95 <= 10_000,
            _sha256(explain.text),
        )
    except Exception as exc:  # noqa: BLE001 - matrix preserves every per-case failure.
        return PerformanceCaseResult(
            case.case_id,
            "ERROR",
            False,
            case.function_families,
            case.plan_family,
            "",
            case.load_tier,
            0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            False,
            "",
            f"{type(exc).__name__}: {exc}",
        )


def _load_tier(case: CorrectnessCase) -> str:
    heavy_markers = {
        "temporal",
        "crossing_window",
        "event_candidate",
        "stage_rank",
        "composite_grouped_aggregate",
        "prefix_long_horizon",
    }
    if any(marker in case.plan_family for marker in heavy_markers):
        return "heavy"
    if case.plan_family in {"direct_column", "controlled_expression"}:
        return "light"
    return "medium"


def _groups(results):
    groups: Dict[str, Dict[str, list]] = {
        "function_family": {},
        "plan_family": {},
        "load_tier": {},
    }
    for result in results:
        for family in result.function_families:
            groups["function_family"].setdefault(family, []).append(result)
        groups["plan_family"].setdefault(result.plan_family, []).append(result)
        groups["load_tier"].setdefault(result.load_tier, []).append(result)
    return {
        dimension: {
            name: {
                "count": len(items),
                "passed": sum(item.status == "PASS" for item in items),
                "max_p95_ms": max((item.execute_p95_ms for item in items), default=0.0),
            }
            for name, items in sorted(values.items())
        }
        for dimension, values in groups.items()
    }


def _percentile(ordered, fraction):
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return round(float(ordered[index]), 6)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"
