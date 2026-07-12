from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.pipeline import compile_official


CASES = (
    ("sum_volume_5", "SUM", ">", 100_000_000),
    ("avg_volume_5", "AVG", ">", 20_000_000),
    ("max_volume_5", "MAX", ">", 50_000_000),
    ("min_volume_5", "MIN", ">", 1_000_000),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect grouped aggregate evidence on a real Doris snapshot"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase14_aggregate_doris.json")
    parser.add_argument("--report-output", default="reports/phase14_aggregate_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    dates = [
        row[0]
        for row in _query_rows(
            args,
            f"SELECT bizdate FROM `{args.database}`.`hsj_stock_hq_basic` "
            "GROUP BY bizdate ORDER BY bizdate DESC LIMIT 5",
        )
    ]
    latest_date = dates[0]
    literals = ",".join(f"'{item}'" for item in dates)
    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    if not doris_versions:
        raise RuntimeError("SHOW FRONTENDS did not expose a Doris build version")

    results = []
    for name, function, comparator, bound in CASES:
        source = (
            f"indicator('沪', '', '成交量', '近5日', '', '{function}', '') "
            f"{comparator} {bound}"
        )
        reference_sql = (
            "WITH qualified AS ("
            "SELECT b.mktcode,b.tgtcode "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.mktcode=1 AND b.bizdate IN ({literals}) "
            "GROUP BY b.mktcode,b.tgtcode "
            f"HAVING {function}(b.volume) {comparator} {bound}) "
            "SELECT a.mktcode,a.tgtcode,a.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS a "
            "INNER JOIN qualified AS q ON q.mktcode=a.mktcode AND q.tgtcode=a.tgtcode "
            f"WHERE a.bizdate='{latest_date}'"
        )
        expected = {tuple(row[:3]) for row in _query_rows(args, reference_sql)}
        generated_sql = compile_official(source).backend["sql"]
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {
                tuple(row[:3]) for row in _query_rows(args, generated_sql)
            }
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        results.append(
            {
                "name": name,
                "source": source,
                "generated_sql": generated_sql,
                "reference_sql": reference_sql,
                "expected_count": len(expected),
                "actual_count": len(actual),
                "expected_sha256": _row_hash(expected),
                "actual_sha256": _row_hash(actual),
                "matched": expected == actual,
                "missing_sample": sorted(expected - actual)[:10],
                "extra_sample": sorted(actual - expected)[:10],
                "elapsed_ms": timings,
                "p95_ms": _nearest_rank(timings, 0.95),
                "set_based": "GROUP BY" in generated_sql
                and "qualified_result" in generated_sql
                and "WHERE (SELECT" not in generated_sql,
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": _query_rows(args, "SELECT VERSION()")[0][0],
        "latest_five_sessions": dates,
        "repeats": args.repeats,
        "status": "PASS"
        if all(item["matched"] and item["set_based"] for item in results)
        else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "set_based": sum(item["set_based"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _query_rows(args, sql: str):
    command = [
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
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [line.split("\t") for line in result.stdout.splitlines() if line.strip()]


def _row_hash(rows) -> str:
    payload = "\n".join("\t".join(map(str, row)) for row in sorted(rows))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _nearest_rank(values, quantile: float):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _write_report(report, json_output: str, markdown_output: str) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Phase 14 集合式分组聚合真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 行集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 集合式计划：`{report['set_based']}/{report['total']}`",
        "",
        "| 场景 | 预期行数 | 实际行数 | 哈希一致 | 集合式 | P95 ms |",
        "|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['expected_count']} | {item['actual_count']} | "
            f"{'是' if item['matched'] else '否'} | {'是' if item['set_based'] else '否'} | "
            f"{item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> reference SQL 使用显式最近五个交易日、GROUP BY/HAVING 和最新快照连接；编译器 SQL 独立生成派生资格集合。证据同时要求完整行集哈希一致并确认生成 SQL 不含每只股票相关标量聚合。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
