from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import time
from pathlib import Path

from findsl.official.backend.doris import render_doris
from findsl.official.lowering import lower_official_ast
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.planner import plan_physical
from findsl.official.physical.statistics import default_physical_statistics
from findsl.official.physical.strategies import default_physical_strategies
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Phase 6C set-based prefix CTE/Join Doris evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--json-output", default="reports/phase6c_set_prefix_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase6c_set_prefix_doris.md"
    )
    args = parser.parse_args()
    if args.warmups < 0 or args.repeats <= 0:
        parser.error("warmups must be non-negative and repeats must be positive")

    catalog = default_physical_catalog()
    physical_statistics = default_physical_statistics(catalog)
    strategies = default_physical_strategies(catalog)
    analyzer = OfficialSemanticAnalyzer(_resolve_indicator_meta)
    schemas = _load_schemas(args, catalog)
    results = []

    for strategy in strategies.strategies:
        threshold = 1000 if "均量线" in strategy.indicator_id else 10
        source = (
            f"indicator('', '', '{strategy.indicator_id}', '', '', '', '') "
            f"> {threshold}"
        )
        typed = analyzer.analyze(parse_official_slot(source, mode="strict"))
        logical = lower_official_ast(
            typed,
            domain_registry=default_official_registry(),
        )
        direct = plan_physical(
            logical,
            catalog,
            statistics=physical_statistics,
            strategies=None,
        )
        prefix = plan_physical(
            logical,
            catalog,
            statistics=physical_statistics,
            strategies=strategies,
            allow_shadow_strategies=True,
        )
        if direct.selected_strategy != "direct_column":
            raise RuntimeError(f"unexpected direct strategy: {direct.selected_strategy}")
        if prefix.selected_strategy != strategy.strategy_id:
            raise RuntimeError(
                f"unexpected prefix strategy for {strategy.indicator_id}: "
                f"{prefix.selected_strategy}"
            )
        direct_sql = render_doris(direct.plan, catalog).sql
        prefix_sql = render_doris(prefix.plan, catalog).sql
        direct_run = _benchmark(args, direct_sql)
        prefix_run = _benchmark(args, prefix_sql)
        direct_explain = _explain(args, direct_sql)
        prefix_explain = _explain(args, prefix_sql)
        direct_scans = _scan_metrics(direct_explain, schemas)
        prefix_scans = _scan_metrics(prefix_explain, schemas)
        matched = (
            direct_run["row_count"] == prefix_run["row_count"]
            and direct_run["sha256"] == prefix_run["sha256"]
        )
        speedup = (
            direct_run["median_ms"] / prefix_run["median_ms"]
            if prefix_run["median_ms"]
            else None
        )
        structural = (
            "WITH prefix_anchor_rows AS" in prefix_sql
            and "prefix_values AS" in prefix_sql
            and " INNER JOIN " in prefix_sql
            and " LEFT JOIN " in prefix_sql
            and "SELECT (" not in prefix_sql
        )
        results.append(
            {
                "strategy_id": strategy.strategy_id,
                "indicator_id": strategy.indicator_id,
                "window": strategy.window,
                "source": source,
                "direct_strategy": direct.selected_strategy,
                "prefix_strategy": prefix.selected_strategy,
                "direct_sql": direct_sql,
                "prefix_sql": prefix_sql,
                "direct": direct_run,
                "prefix": prefix_run,
                "matched": matched,
                "structural_contract": structural,
                "median_speedup": round(speedup, 6) if speedup is not None else None,
                "prefix_faster": speedup is not None and speedup > 1.0,
                "direct_explain_sha256": _hash_text(direct_explain),
                "prefix_explain_sha256": _hash_text(prefix_explain),
                "direct_scans": direct_scans,
                "prefix_scans": prefix_scans,
                "direct_projected_logical_bytes": sum(
                    item["projected_logical_bytes"] for item in direct_scans
                ),
                "prefix_projected_logical_bytes": sum(
                    item["projected_logical_bytes"] for item in prefix_scans
                ),
                "direct_explain_excerpt": "\n".join(direct_explain.splitlines()[:100]),
                "prefix_explain_excerpt": "\n".join(prefix_explain.splitlines()[:140]),
            }
        )

    passed = all(
        item["matched"] and item["structural_contract"] for item in results
    )
    faster = sum(item["prefix_faster"] for item in results)
    speedups = [item["median_speedup"] for item in results]
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "status": "PASS" if passed else "FAIL",
        "warmups": args.warmups,
        "repeats": args.repeats,
        "case_count": len(results),
        "matched": sum(item["matched"] for item in results),
        "structural_contracts": sum(
            item["structural_contract"] for item in results
        ),
        "prefix_faster": faster,
        "all_prefix_faster": faster == len(results),
        "median_speedup": round(statistics.median(speedups), 6),
        "min_speedup": round(min(speedups), 6),
        "max_speedup": round(max(speedups), 6),
        "cost_method": (
            "EXPLAIN scan cardinality multiplied by projected column logical widths; "
            "reported as a conservative model, not measured storage bytes"
        ),
        "results": results,
    }
    _write(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _benchmark(args, sql: str):
    for _ in range(args.warmups):
        _query(args, sql)
    elapsed = []
    rows = []
    for _ in range(args.repeats):
        started = time.perf_counter_ns()
        rows = _query(args, sql)
        elapsed.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
    digest = _row_hash(rows)
    return {
        "row_count": len(rows),
        "sha256": digest,
        "elapsed_ms": elapsed,
        "median_ms": round(statistics.median(elapsed), 4),
        "p95_ms": _nearest_rank(elapsed, 0.95),
    }


def _query(args, sql: str):
    result = subprocess.run(
        [
            str(args.client),
            "--default-character-set=utf8mb4",
            "-h",
            args.host,
            "-P",
            str(args.port),
            "-u",
            args.user,
            "-N",
            "-B",
            "-e",
            sql,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [tuple(line.split("\t")) for line in result.stdout.splitlines() if line]


def _explain(args, sql: str) -> str:
    return "\n".join("\t".join(row) for row in _query(args, f"EXPLAIN {sql}"))


def _load_schemas(args, catalog):
    schemas = {}
    for resource in catalog.resources:
        rows = _query(
            args,
            f"DESC `{resource.database}`.`{resource.table}`",
        )
        schemas[resource.table] = {
            row[0]: row[1] for row in rows if len(row) >= 2
        }
    return schemas


def _scan_metrics(explain: str, schemas):
    lines = explain.splitlines()
    scans = []
    for index, line in enumerate(lines):
        if "VOlapScanNode" not in line:
            continue
        block = lines[index : index + 24]
        table = None
        cardinality = None
        partitions = None
        projections = []
        for detail in block:
            table_match = re.search(r"TABLE:\s+(?:[A-Za-z0-9_]+\.)?([A-Za-z0-9_]+)", detail)
            if table_match:
                table = table_match.group(1)
            cardinality_match = re.search(r"cardinality=([0-9]+)", detail)
            if cardinality_match:
                cardinality = int(cardinality_match.group(1))
            partition_match = re.search(r"partitions=([0-9]+/[0-9]+)", detail)
            if partition_match:
                partitions = partition_match.group(1)
            if "final projections:" in detail:
                projections = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\[#", detail)
                break
        schema = schemas.get(table or "", {})
        row_width = sum(_logical_width(schema.get(column, "")) for column in projections)
        scans.append(
            {
                "table": table,
                "cardinality": cardinality,
                "partitions": partitions,
                "projected_columns": projections,
                "projected_column_count": len(projections),
                "logical_row_width_bytes": row_width,
                "projected_logical_bytes": (cardinality or 0) * row_width,
            }
        )
    return scans


def _logical_width(type_name: str) -> int:
    normalized = type_name.upper()
    if "TINYINT" in normalized or "BOOLEAN" in normalized:
        return 1
    if "SMALLINT" in normalized:
        return 2
    if normalized.startswith("INT") or "DATEV2" in normalized or normalized == "DATE":
        return 4
    if any(token in normalized for token in ("BIGINT", "LARGEINT", "DOUBLE", "DATETIME")):
        return 8
    if any(token in normalized for token in ("DECIMAL", "FLOAT")):
        return 8
    match = re.search(r"(?:CHAR|VARCHAR)\((\d+)\)", normalized)
    if match:
        return min(int(match.group(1)), 64)
    return 16


def _row_hash(rows) -> str:
    payload = "\n".join("\t".join(row) for row in sorted(set(rows)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _write(report, json_output: str, markdown_output: str) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Phase 6C 集合式前缀 Join Doris 证据",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 状态：`{report['status']}`",
        f"- 完整行集哈希一致：`{report['matched']}/{report['case_count']}`",
        f"- 关系结构合同：`{report['structural_contracts']}/{report['case_count']}`",
        f"- 前缀路径更快：`{report['prefix_faster']}/{report['case_count']}`",
        f"- 中位加速比：`{report['median_speedup']:.3f}x`",
        f"- 加速范围：`{report['min_speedup']:.3f}x` 至 `{report['max_speedup']:.3f}x`",
        "",
        "| 指标 | 窗口 | 行数 | 直接列中位(ms) | 前缀中位(ms) | 加速比 | 哈希 | CTE/Join |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for item in report["results"]:
        lines.append(
            f"| {item['indicator_id']} | {item['window']} | {item['direct']['row_count']} | "
            f"{item['direct']['median_ms']:.4f} | {item['prefix']['median_ms']:.4f} | "
            f"{item['median_speedup']:.3f}x | {'PASS' if item['matched'] else 'FAIL'} | "
            f"{'PASS' if item['structural_contract'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "> 投影列成本按 EXPLAIN 扫描基数乘以字段逻辑宽度计算，是保守模型，不冒充 Doris 实测存储字节。",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
