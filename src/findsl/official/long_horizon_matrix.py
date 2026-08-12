from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Tuple


class LongHorizonMatrixError(ValueError):
    pass


@dataclass(frozen=True)
class LongHorizonCase:
    case_id: str
    dsl: str
    indicator: str
    aggregation: str
    target_speedup: float


def load_long_horizon_manifest(path: Path) -> Tuple[LongHorizonCase, ...]:
    cases = []
    seen = set()
    expected = {"case_id", "dsl", "indicator", "aggregation", "target_speedup"}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict) or set(raw) != expected:
            raise LongHorizonMatrixError(f"invalid long-horizon case at line {line_number}")
        case = LongHorizonCase(
            case_id=str(raw["case_id"]),
            dsl=str(raw["dsl"]),
            indicator=str(raw["indicator"]),
            aggregation=str(raw["aggregation"]).upper(),
            target_speedup=float(raw["target_speedup"]),
        )
        if case.case_id in seen:
            raise LongHorizonMatrixError(f"duplicate long-horizon case_id: {case.case_id}")
        if case.aggregation not in {"SUM", "AVG"} or case.target_speedup <= 0:
            raise LongHorizonMatrixError(f"invalid long-horizon contract: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not 4 <= len(cases) <= 6:
        raise LongHorizonMatrixError("long-horizon matrix must contain four to six workloads")
    return tuple(cases)


def summarize_long_horizon_reports(
    cases: Iterable[LongHorizonCase],
    reports: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    case_list = tuple(cases)
    report_list = tuple(reports)
    if len(case_list) != len(report_list):
        raise LongHorizonMatrixError("case/report count mismatch")
    rows = []
    for case, report in zip(case_list, report_list):
        hash_match = bool(report.get("complete_result_hash_match"))
        row_match = bool(report.get("row_count_match"))
        speedup = float(report.get("speedup") or 0.0)
        optimized_p95_ms = float((report.get("optimized") or {}).get("p95_ms") or float("inf"))
        passed = bool(hash_match and row_match and speedup >= case.target_speedup and optimized_p95_ms < 10_000)
        rows.append(
            {
                "case_id": case.case_id,
                "indicator": case.indicator,
                "aggregation": case.aggregation,
                "dsl": case.dsl,
                "target_speedup": case.target_speedup,
                "speedup": speedup,
                "baseline_median_ms": float((report.get("baseline") or {}).get("median_ms") or 0.0),
                "optimized_median_ms": float((report.get("optimized") or {}).get("median_ms") or 0.0),
                "optimized_p95_ms": optimized_p95_ms,
                "complete_result_hash_match": hash_match,
                "row_count_match": row_match,
                "result_row_count": int(report.get("result_row_count") or 0),
                "baseline_strategy": report.get("baseline_strategy"),
                "optimized_strategy": report.get("optimized_strategy"),
                "optimized_resource_id": report.get("optimized_resource_id"),
                "status": "PASS" if passed else "FAIL",
            }
        )
    speedups = [row["speedup"] for row in rows]
    return {
        "schema_version": 1,
        "workload_count": len(rows),
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "target_speedup": min((row["target_speedup"] for row in rows), default=0.0),
        "target_met": bool(rows and all(row["status"] == "PASS" for row in rows)),
        "all_complete_result_hashes_match": bool(rows and all(row["complete_result_hash_match"] for row in rows)),
        "all_row_counts_match": bool(rows and all(row["row_count_match"] for row in rows)),
        "all_optimized_p95_under_10s": bool(rows and all(row["optimized_p95_ms"] < 10_000 for row in rows)),
        "minimum_speedup": min(speedups) if speedups else 0.0,
        "median_speedup": statistics.median(speedups) if speedups else 0.0,
        "workloads": rows,
        "metric_scope": "five stratified 5000-session prefix workloads; separate from Phase 6C set-prefix and short-window measurements",
    }


def write_long_horizon_matrix(report: Mapping[str, Any], json_path: Path, markdown_path: Path) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 官方 20 年数据长周期工作负载矩阵",
        "",
        f"- 状态：`{report.get('status')}`",
        f"- 工作负载：`{report.get('workload_count')}`",
        f"- 最低加速比：`{float(report.get('minimum_speedup') or 0):.3f}x`",
        f"- 加速比中位数：`{float(report.get('median_speedup') or 0):.3f}x`",
        f"- 全部完整结果哈希一致：`{report.get('all_complete_result_hashes_match')}`",
        f"- 全部优化 P95 小于 10 秒：`{report.get('all_optimized_p95_under_10s')}`",
        "",
        "| Workload | 指标 | 聚合 | 基线中位数 ms | 优化中位数 ms | 优化 P95 ms | 加速比 | 哈希一致 | 状态 |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report.get("workloads") or []:
        lines.append(
            f"| {row['case_id']} | {row['indicator']} | {row['aggregation']} | "
            f"{row['baseline_median_ms']:.3f} | {row['optimized_median_ms']:.3f} | "
            f"{row['optimized_p95_ms']:.3f} | {row['speedup']:.3f}x | "
            f"{row['complete_result_hash_match']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## 口径边界",
            "",
            "本矩阵只比较五类 5000 个交易日聚合的完整结果和 Doris Profile 耗时。它不与短窗口、集合式前缀或外部集群基准混为一个加速数字。",
        ]
    )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
