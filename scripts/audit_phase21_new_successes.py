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
    parser.add_argument(
        "--require-event-candidates",
        action="store_true",
        help="Require every newly successful query to use keyed event candidates",
    )
    parser.add_argument(
        "--require-date-algebra",
        action="store_true",
        help="Require normalized date/open-limit contracts for every new success",
    )
    parser.add_argument(
        "--require-event-semantics",
        action="store_true",
        help=(
            "Require every new event success to materialize either a keyed "
            "candidate-set plan or an event projection before temporal evaluation"
        ),
    )
    parser.add_argument(
        "--require-default-price-events",
        action="store_true",
        help=(
            "Require each new success to carry the documented empty event "
            "indicator default as 最新价 through Logical IR and Doris SQL"
        ),
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
        candidate_sets = [
            node
            for node in _walk_dicts(physical_plan)
            if node.get("kind") == "PhysicalCandidateSetOperation"
        ]
        checks = {
            "backend_validation": payload["backend"]["validation_passed"],
            "no_placeholder_predicate": not re.search(r"\b1\s*=\s*[01]\b", sql),
            "approximation_materialized": True,
            "aggregate_materialized": True,
            "temporal_materialized": True,
            "rank_materialized": True,
            "period_scalar_materialized": True,
            "event_candidate_materialized": True,
            "date_algebra_materialized": True,
            "event_semantics_materialized": True,
            "default_price_event_materialized": True,
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
        if args.require_event_candidates or candidate_sets:
            checks["event_candidate_materialized"] = bool(candidate_sets) and all(
                candidate.get("key_semantics") == "security"
                and candidate.get("output_date_policy") == "latest_anchor"
                and candidate.get("operation") in {"intersect", "union", "except"}
                for candidate in candidate_sets
            ) and any(token in sql for token in (" INTERSECT ", " UNION ", " EXCEPT "))
            if any(candidate.get("operation") == "except" for candidate in candidate_sets):
                checks["event_candidate_materialized"] &= (
                    " EXCEPT " in sql and "`event_rows`.`event_0` = TRUE" in sql
                )
        if args.require_date_algebra:
            checks["date_algebra_materialized"] = _date_algebra_materialized(
                payload,
                source,
                sql,
            )
        if args.require_event_semantics:
            checks["event_semantics_materialized"] = _event_semantics_materialized(
                payload,
                sql,
            )
        if args.require_default_price_events:
            checks["default_price_event_materialized"] = (
                _default_price_event_materialized(payload, sql)
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
        "require_period_scalars": args.require_period_scalars,
        "require_event_candidates": args.require_event_candidates,
        "require_date_algebra": args.require_date_algebra,
        "require_event_semantics": args.require_event_semantics,
        "require_default_price_events": args.require_default_price_events,
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


def _event_semantics_materialized(payload, sql: str) -> bool:
    strategy = payload["physical"]["selected_strategy"]
    physical_nodes = list(_walk_dicts(payload["physical"]["plan"]))
    kinds = {node.get("kind") for node in physical_nodes}
    event_kinds = {
        "PhysicalCrossing",
        "PhysicalExtreme",
        "PhysicalPattern",
        "PhysicalPosition",
    }
    if "PhysicalEventFilter" in kinds and kinds & event_kinds:
        return " AS `event_" in sql and "`event_rows`.`event_" in sql
    if strategy == "temporal_event_projection":
        return (
            {"PhysicalTemporal", "PhysicalEventProjection"}.issubset(kinds)
            and "LAG(" in sql
            and "source_rows AS" in sql
            and "temporal_metrics AS" in sql
            and (
                "bucket_rows AS" in sql
                or {"sequenced_rows AS", "matched_rows AS", "runs AS"}.issubset(
                    set(re.findall(r"\b([a-z_]+ AS)\b", sql))
                )
            )
        )
    if strategy.startswith("event_candidate_"):
        operations = {
            node.get("operation")
            for node in physical_nodes
            if node.get("kind") == "PhysicalCandidateSetOperation"
        }
        return bool(operations) and all(
            operation in {"intersect", "union", "except"}
            for operation in operations
        ) and any(f" {operation.upper()} " in sql for operation in operations)
    return False


def _default_price_event_materialized(payload, sql: str) -> bool:
    default_slots = {
        "cross_above": "indicator_name_1",
        "cross_down": "indicator_name_1",
        "close_together": "indicator_name_1",
        "reset": "indicator_name_1",
        "record_high": "indicator_name",
        "record_low": "indicator_name",
        "position": "indicator_name",
    }
    calls = [
        node
        for node in _walk_dicts(payload["logical"]["plan"])
        if node.get("kind") == "CallExpr" and node.get("name") in default_slots
    ]
    normalized = [
        node
        for node in calls
        if node.get("binding", {}).get("slots", {}).get(default_slots[node["name"]])
        == "最新价"
    ]
    return bool(normalized) and "`lastPx` / 10000.0" in sql


def _date_algebra_materialized(payload, source: str, sql: str) -> bool:
    physical_nodes = list(_walk_dicts(payload["physical"]["plan"]))
    logical_nodes = list(_walk_dicts(payload["logical"]["plan"]))
    if re.search(r"limit\s+\d+\s*,\s*-1\s*$", source, flags=re.IGNORECASE):
        open_limits = [
            node
            for node in physical_nodes
            if node.get("kind") == "PhysicalLimit" and node.get("count") is None
        ]
        expected_limits = {
            f"LIMIT {9223372036854775807 - int(node.get('offset', 0))}"
            for node in open_limits
        }
        if not open_limits or not all(limit in sql for limit in expected_limits):
            return False
    if "0.5年" in source:
        normalized_temporal = any(
            node.get("unit") == "月" and node.get("threshold") == 6
            for node in physical_nodes
        )
        if not normalized_temporal or "'MONTH'" not in sql:
            return False

    contracts = [
        node["date_constraint"]
        for node in logical_nodes
        if node.get("kind") == "CallExpr"
        and isinstance(node.get("date_constraint"), dict)
        and node["date_constraint"].get("constraint_kind")
        not in {None, "unspecified"}
    ]
    for contract in contracts:
        kind = contract.get("constraint_kind")
        if kind == "expression":
            return False
        if kind in {"exact", "calendar_range"}:
            for boundary in (contract.get("start"), contract.get("end")):
                if boundary and boundary not in sql:
                    return False
        elif kind in {"before_anchor_sessions", "after_anchor_sessions"}:
            direction = "before" if kind.startswith("before") else "after"
            if not any(
                (
                    node.get("kind") == "PhysicalSessionBoundaryRange"
                    and node.get("boundary_kind") == "anchor"
                    and node.get("direction") == direction
                    and node.get("amount") == contract.get("amount")
                    and node.get("month") == contract.get("month")
                    and node.get("day") == contract.get("day")
                )
                or (
                    node.get("kind") == "boundary_sessions"
                    and node.get("boundary_kind") == "anchor"
                    and node.get("boundary_direction") == direction
                    and node.get("lookback_sessions") == contract.get("amount")
                    and node.get("anchor_month") == contract.get("month")
                    and node.get("anchor_day") == contract.get("day")
                )
                for node in physical_nodes
            ):
                return False
        elif kind == "session_slice" and contract.get("offset"):
            if not any(
                (
                    node.get("kind") == "PhysicalRecentSessions"
                    and node.get("amount") == contract.get("amount")
                    and node.get("offset") == contract.get("offset")
                )
                or (
                    node.get("kind") == "session_slice"
                    and node.get("lookback_sessions") == contract.get("amount")
                    and node.get("session_offset") == contract.get("offset")
                )
                for node in physical_nodes
            ):
                return False
        elif kind == "recent_calendar":
            if not any(
                (
                    node.get("kind") == "PhysicalDynamicDateRange"
                    and node.get("range_kind") == "recent"
                    and node.get("amount") == contract.get("amount")
                    and node.get("unit") == contract.get("unit")
                )
                or (
                    node.get("kind") == "recent_calendar"
                    and node.get("calendar_amount") == contract.get("amount")
                    and node.get("calendar_unit") == contract.get("unit")
                )
                for node in physical_nodes
            ):
                return False
    physical_date_contract = any(
        node.get("kind")
        in {
            "PhysicalDynamicDateRange",
            "PhysicalSessionBoundaryRange",
            "PhysicalRecentSessions",
            "boundary_sessions",
            "calendar_range",
            "recent_calendar",
            "session_slice",
        }
        for node in physical_nodes
    )
    return (
        bool(contracts)
        or physical_date_contract
        or "limit" in source.lower()
        or "0.5年" in source
    )


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
            "逐条重新编译基线失败而当前版本成功的问句，并检查：后端 AST 验证通过；不存在 `1=0/1=1` 占位谓词；近似比较包含配置化容差表达式；聚合函数同时进入 Physical IR 和 SQL；`CONS/EXIST` 进入时序关系；`rank` 生成真实窗口排名；命名周期标量显式携带 `collapse_latest` 合同并生成 `MAX_BY`；事件组合显式声明证券键集合与最新快照输出策略；扩展日期、分数量词和开放分页必须进入 Typed/Physical 合同并在 SQL 中可见。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
