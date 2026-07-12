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
    parser.add_argument(
        "--require-period-scalars",
        action="store_true",
        help="Require every newly successful query to materialize a period-end scalar",
    )
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
        physical_plan = payload["physical"]["plan"]
        physical = json.dumps(physical_plan, ensure_ascii=False, sort_keys=True)
        sql = payload["backend"]["sql"]
        named_scalars = [
            node
            for node in _walk_dicts(physical_plan)
            if node.get("kind") == "PhysicalNamedScalar"
        ]
        checks = {
            "backend_validation": payload["backend"]["validation_passed"],
            "no_placeholder_predicate": not re.search(r"\b1\s*=\s*[01]\b", sql),
            "approximation_materialized": True,
            "aggregate_materialized": True,
            "temporal_materialized": True,
            "rank_materialized": True,
            "period_scalar_materialized": True,
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
                        "PhysicalStageRank",
                    )
                )
                and "ROW_NUMBER() OVER" in sql
            )
        period_scalars = [
            scalar for scalar in named_scalars if scalar.get("collapse_latest") is True
        ]
        if args.require_period_scalars or period_scalars:
            checks["period_scalar_materialized"] = bool(period_scalars) and all(
                bool(scalar.get("value_alias")) for scalar in period_scalars
            ) and "MAX_BY(" in sql
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
        "require_period_scalars": args.require_period_scalars,
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


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _write(report, json_output: str, report_output: str) -> None:
    json_path = Path(json_output)
    report_path = Path(report_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 编译器新增成功集假阳性审计",
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
            "逐条重新编译基线失败而当前版本成功的问句，并检查：后端 AST 验证通过；不存在 `1=0/1=1` 占位谓词；近似比较包含配置化容差表达式；聚合函数同时进入 Physical IR 和 SQL；`CONS/EXIST` 进入时序关系；`rank` 生成真实窗口排名；命名周期标量显式携带 `collapse_latest` 合同并生成 `MAX_BY`。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
