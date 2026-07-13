from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from findsl.official.backend.executor import (
    DorisExecutionConfig,
    execute_doris_query_digest,
)
from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute newly successful official funnel rows on Doris"
    )
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--performance-target-ms", type=float, default=10_000.0)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    previous = _read_json(Path(args.previous))
    current = _read_json(Path(args.current))
    rows = select_delta_rows(previous, current)
    config = DorisExecutionConfig(
        args.host,
        args.port,
        args.user,
        args.password,
        args.database,
        args.client,
        args.timeout_seconds,
    )
    cases = []
    for row in rows:
        case = {
            "excel_row": row["excel_row"],
            "source": row["source"],
            "selected_strategy": row.get("selected_strategy"),
            "status": "FAIL",
            "row_count": None,
            "result_sha256": None,
            "sql_sha256": None,
            "elapsed_ms": [],
            "p50_ms": None,
            "p95_ms": None,
            "stable_result": False,
            "under_performance_target": False,
            "error": "",
        }
        try:
            sql = compile_official(row["source"]).backend["sql"]
            case["sql_sha256"] = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            executions = [
                execute_doris_query_digest(config, sql) for _ in range(args.repeats)
            ]
            counts = {item.row_count for item in executions}
            hashes = {item.sha256 for item in executions}
            elapsed = [round(item.elapsed_ms, 3) for item in executions]
            case.update(
                {
                    "row_count": executions[-1].row_count,
                    "result_sha256": executions[-1].sha256,
                    "elapsed_ms": elapsed,
                    "p50_ms": _nearest_rank(elapsed, 0.50),
                    "p95_ms": _nearest_rank(elapsed, 0.95),
                    "stable_result": len(counts) == 1 and len(hashes) == 1,
                    "under_performance_target": max(elapsed)
                    < args.performance_target_ms,
                }
            )
            if case["stable_result"] and case["under_performance_target"]:
                case["status"] = "PASS"
        except Exception as exc:
            case["error"] = str(exc)
        cases.append(case)

    passed = bool(cases) and all(item["status"] == "PASS" for item in cases)
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "previous_funnel": str(Path(args.previous).resolve()),
        "current_funnel": str(Path(args.current).resolve()),
        "previous_git_head": previous.get("git_head"),
        "current_git_head": current.get("git_head"),
        "repeats": args.repeats,
        "performance_target_ms": args.performance_target_ms,
        "total": len(cases),
        "passed": sum(item["status"] == "PASS" for item in cases),
        "failed": sum(item["status"] != "PASS" for item in cases),
        "status": "PASS" if passed else "FAIL",
        "cases": cases,
    }
    _write_report(report, Path(args.json_output), Path(args.report_output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def select_delta_rows(previous, current):
    previous_success = {
        item["excel_row"] for item in previous["rows"] if item["new_backend_success"]
    }
    return tuple(
        item
        for item in current["rows"]
        if item["new_backend_success"] and item["excel_row"] not in previous_success
    )


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _nearest_rank(values, quantile: float):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def _write_report(report, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 官方漏斗差量 Doris 执行审计",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 状态：`{report['status']}`",
        f"- 真实执行通过：`{report['passed']}/{report['total']}`",
        f"- 每条重复执行：`{report['repeats']}` 次",
        f"- 性能阈值：`{report['performance_target_ms']:.0f} ms`",
        "",
        "| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |",
        "|---:|---|---:|---:|---:|---|---|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['excel_row']} | {item['selected_strategy']} | "
            f"{item['row_count']} | {_display(item['p50_ms'])} | "
            f"{_display(item['p95_ms'])} | "
            f"{'PASS' if item['stable_result'] else 'FAIL'} | {item['status']} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display(value):
    return "-" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
