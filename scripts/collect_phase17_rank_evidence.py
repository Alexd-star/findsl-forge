from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.pipeline import compile_official


SOURCES = (
    (
        "direct_top_10",
        "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10",
    ),
    (
        "direct_top_10_percent",
        "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10%",
    ),
    (
        "aggregate_avg_top_10",
        "rank('', '', '成交量', 'desc', '近5日', '', 'AVG', '') <= 10",
    ),
    (
        "aggregate_avg_top_10_percent",
        "rank('', '', '成交量', 'desc', '近5日', '', 'AVG', '') <= 10%",
    ),
    (
        "rank_scalar_intersection",
        "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10 and "
        "indicator('', '', '成交额', '今日', '', '', '') > 100000000",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect direct, percentage, aggregate, and set-rank Doris evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase17_rank_doris.json")
    parser.add_argument("--report-output", default="reports/phase17_rank_doris.md")
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
    if len(dates) != 5:
        raise RuntimeError(f"expected five distinct trading sessions, got {len(dates)}")
    latest = dates[0]
    date_5 = ",".join(f"'{item}'" for item in dates)
    table = f"`{args.database}`.`hsj_stock_hq_basic`"
    direct_rank = (
        "SELECT b.mktcode,b.tgtcode,b.bizdate,"
        "ROW_NUMBER() OVER (ORDER BY b.volume DESC,b.mktcode ASC,b.tgtcode ASC) AS rn,"
        "COUNT(*) OVER () AS population "
        f"FROM {table} AS b WHERE b.bizdate='{latest}'"
    )
    aggregate_rank = (
        "WITH metrics AS ("
        "SELECT b.mktcode,b.tgtcode,AVG(b.volume) AS metric "
        f"FROM {table} AS b WHERE b.bizdate IN ({date_5}) "
        "GROUP BY b.mktcode,b.tgtcode), ranked AS ("
        "SELECT m.mktcode,m.tgtcode,m.metric,"
        "ROW_NUMBER() OVER (ORDER BY m.metric DESC,m.mktcode ASC,m.tgtcode ASC) AS rn,"
        "COUNT(*) OVER () AS population FROM metrics AS m) "
    )
    references = {
        "direct_top_10": (
            f"WITH ranked AS ({direct_rank}) "
            "SELECT mktcode,tgtcode,bizdate FROM ranked WHERE rn<=10"
        ),
        "direct_top_10_percent": (
            f"WITH ranked AS ({direct_rank}) "
            "SELECT mktcode,tgtcode,bizdate FROM ranked "
            "WHERE rn<=CEIL(population*10/100.0)"
        ),
        "aggregate_avg_top_10": (
            aggregate_rank
            + "SELECT a.mktcode,a.tgtcode,a.bizdate "
            f"FROM {table} AS a INNER JOIN ranked AS r "
            "ON r.mktcode=a.mktcode AND r.tgtcode=a.tgtcode "
            f"WHERE a.bizdate='{latest}' AND r.rn<=10"
        ),
        "aggregate_avg_top_10_percent": (
            aggregate_rank
            + "SELECT a.mktcode,a.tgtcode,a.bizdate "
            f"FROM {table} AS a INNER JOIN ranked AS r "
            "ON r.mktcode=a.mktcode AND r.tgtcode=a.tgtcode "
            f"WHERE a.bizdate='{latest}' AND r.rn<=CEIL(r.population*10/100.0)"
        ),
        "rank_scalar_intersection": (
            f"WITH ranked AS ({direct_rank}) "
            "SELECT r.mktcode,r.tgtcode,r.bizdate FROM ranked AS r "
            f"INNER JOIN {table} AS b ON b.mktcode=r.mktcode "
            "AND b.tgtcode=r.tgtcode AND b.bizdate=r.bizdate "
            "WHERE r.rn<=10 AND b.turnover>100000000"
        ),
    }

    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    if not doris_versions:
        raise RuntimeError("SHOW FRONTENDS did not expose a Doris build version")

    results = []
    for name, source in SOURCES:
        reference_sql = references[name]
        expected = {tuple(row[:3]) for row in _query_rows(args, reference_sql)}
        generated_sql = compile_official(source).backend["sql"]
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {tuple(row[:3]) for row in _query_rows(args, generated_sql)}
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join("\t".join(row) for row in _query_rows(args, "EXPLAIN " + generated_sql))
        percentage = "percent" in name
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
                "row_number_window": "ROW_NUMBER() OVER" in generated_sql,
                "partition_count_window": ("COUNT(*) OVER" in generated_sql) == percentage,
                "set_intersection": ("INTERSECT" in generated_sql) == (name == "rank_scalar_intersection"),
                "explain_sha256": hashlib.sha256(explain.encode("utf-8")).hexdigest(),
                "explain_excerpt": explain[:4000],
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": _query_rows(args, "SELECT VERSION()")[0][0],
        "basic_row_count": int(_query_rows(args, f"SELECT COUNT(*) FROM {table}")[0][0]),
        "latest_five_sessions": dates,
        "repeats": args.repeats,
        "status": "PASS"
        if all(
            item["matched"]
            and item["row_number_window"]
            and item["partition_count_window"]
            and item["set_intersection"]
            for item in results
        )
        else "FAIL",
        "matched": sum(item["matched"] for item in results),
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
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 17 类型化排名真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 基础行情表：`{report['basic_row_count']}` 行",
        f"- 完整行集哈希一致：`{report['matched']}/{report['total']}`",
        "",
        "| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |",
        "|---|---:|---:|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['expected_count']} | {item['actual_count']} | "
            f"{'是' if item['matched'] else '否'} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> reference SQL 独立使用 ROW_NUMBER、COUNT、CEIL、GROUP BY 和集合交集。百分比边界按实际候选集基数向上取整；聚合排名先形成每证券度量，再执行窗口排名。并列值由 mktcode、tgtcode 稳定裁决。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
