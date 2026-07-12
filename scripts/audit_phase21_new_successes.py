from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit every Phase 21 newly successful query")
    parser.add_argument(
        "--baseline",
        default="submission_artifacts/evidence_snapshots/phase20_capability_funnel.json",
    )
    parser.add_argument("--current", default="reports/phase21_capability_funnel.json")
    parser.add_argument("--json-output", default="reports/phase21_new_success_audit.json")
    parser.add_argument("--report-output", default="reports/phase21_new_success_audit.md")
    args = parser.parse_args()

    baseline = _rows(args.baseline)
    current = _rows(args.current)
    baseline_by_row = {item["excel_row"]: item for item in baseline}
    gained = [
        item
        for item in current
        if item["new_backend_success"]
        and not baseline_by_row[item["excel_row"]]["new_backend_success"]
    ]

    results = []
    for row in gained:
        source = row["source"]
        payload = compile_official(source).to_dict()
        physical = json.dumps(payload["physical"]["plan"], ensure_ascii=False, sort_keys=True)
        sql = payload["backend"]["sql"]
        checks = {
            "backend_validation": payload["backend"]["validation_passed"],
            "no_placeholder_predicate": not re.search(r"\b1\s*=\s*[01]\b", sql),
            "approximation_materialized": True,
            "aggregate_materialized": True,
            "temporal_materialized": True,
            "rank_materialized": True,
        }
        if "~=" in source:
            checks["approximation_materialized"] = "ABS(" in sql and "GREATEST(" in sql
        aggregate_functions = re.findall(
            r"['\"](GROWTH_RISE|GROWTH_FALL|SUM|AVG|MAX|MIN)['\"]",
            source,
            flags=re.IGNORECASE,
        )
        for function in aggregate_functions:
            normalized = function.lower()
            physical_ok = normalized in physical
            sql_ok = (
                ("MIN_BY(" in sql and "MAX_BY(" in sql) or "LAG(" in sql
                if normalized.startswith("growth_")
                else f"{function.upper()}(" in sql
            )
            checks["aggregate_materialized"] &= physical_ok and sql_ok
        if re.search(r"['\"](?:CONS|EXIST)[^'\"]*['\"]", source, flags=re.IGNORECASE):
            checks["temporal_materialized"] = any(
                kind in physical
                for kind in (
                    "PhysicalTemporal\"",
                    "PhysicalTemporalAggregate",
                    "PhysicalTemporalRank",
                )
            ) and any(token in sql for token in ("temporal_metrics", "aggregate_temporal_metrics"))
        if re.search(r"\brank\s*\(", source, flags=re.IGNORECASE):
            checks["rank_materialized"] = (
                any(
                    kind in physical
                    for kind in (
                        "PhysicalRank",
                        "PhysicalAggregateRank",
                        "PhysicalTemporalRank",
                    )
                )
                and "ROW_NUMBER() OVER" in sql
            )
        passed = all(checks.values())
        results.append(
            {
                "excel_row": row["excel_row"],
                "source": source,
                "strategy": payload["physical"]["selected_strategy"],
                "plan_kind": payload["physical"]["plan"]["kind"],
                "checks": checks,
                "passed": passed,
            }
        )

    report = {
        "schema_version": 1,
        "baseline": args.baseline,
        "current": args.current,
        "new_successes": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "status": "PASS" if all(item["passed"] for item in results) else "FAIL",
        "strategies": dict(Counter(item["strategy"] for item in results)),
        "results": results,
    }
    _write(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _rows(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))["rows"]


def _write(report, json_output: str, report_output: str) -> None:
    json_path = Path(json_output)
    report_path = Path(report_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 21 新增成功集假阳性审计",
        "",
        f"- 状态：`{report['status']}`",
        f"- 新增成功：`{report['new_successes']}`",
        f"- 全部检查通过：`{report['passed']}`",
        f"- 检查失败：`{report['failed']}`",
        "",
        "## 策略分布",
        "",
        "| 策略 | 数量 |",
        "|---|---:|",
    ]
    for strategy, count in sorted(report["strategies"].items()):
        lines.append(f"| `{strategy}` | {count} |")
    lines.extend(
        [
            "",
            "## 审计合同",
            "",
            "逐条重新编译 Phase 20 失败而 Phase 21 成功的问句，并检查：后端 AST 验证通过；不存在 `1=0/1=1` 占位谓词；近似比较包含配置化容差表达式；聚合函数同时进入 Physical IR 和 SQL；`CONS/EXIST` 进入时序关系；`rank` 生成真实窗口排名。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
