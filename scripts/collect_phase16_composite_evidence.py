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
        "latest_equals_min_100_sessions",
        "indicator('', '', '成交量', '今日', '', '', '') = "
        "indicator('', '', '成交量', '近100个交易日', '', 'MIN', '')",
    ),
    (
        "cross_resource_average_ratio",
        "indicator('', '', '主力净流入', '近5日', '', 'AVG', '') / "
        "indicator('', '', '成交额', '近5日', '', 'AVG', '') < 20%",
    ),
    (
        "two_windows_with_latest_scalar",
        "indicator('', '', '成交量', '7日内', '', 'AVG', '') = "
        "indicator('', '', '成交量', '5日内', '', 'MIN', '') and "
        "indicator('', '', '涨幅', '今天', '', '', '') > 2%",
    ),
    (
        "nonempty_two_window_comparison",
        "indicator('', '', '成交量', '7日内', '', 'AVG', '') > "
        "indicator('', '', '成交量', '5日内', '', 'MIN', '')",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect named composite aggregate evidence on a real Doris snapshot"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase16_composite_doris.json")
    parser.add_argument("--report-output", default="reports/phase16_composite_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    dates = [
        row[0]
        for row in _query_rows(
            args,
            f"SELECT bizdate FROM `{args.database}`.`hsj_stock_hq_basic` "
            "GROUP BY bizdate ORDER BY bizdate DESC LIMIT 100",
        )
    ]
    if len(dates) != 100:
        raise RuntimeError(f"expected 100 distinct trading sessions, got {len(dates)}")
    latest = dates[0]
    date_100 = _sql_literals(dates[:100])
    date_7 = _sql_literals(dates[:7])
    date_5 = _sql_literals(dates[:5])
    references = {
        "latest_equals_min_100_sessions": (
            "WITH m AS ("
            "SELECT b.mktcode,b.tgtcode,MIN(b.volume) AS metric "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate IN ({date_100}) GROUP BY b.mktcode,b.tgtcode) "
            "SELECT a.mktcode,a.tgtcode,a.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS a "
            "INNER JOIN m ON m.mktcode=a.mktcode AND m.tgtcode=a.tgtcode "
            f"WHERE a.bizdate='{latest}' AND a.volume=m.metric"
        ),
        "cross_resource_average_ratio": (
            "WITH n AS ("
            "SELECT b.mktcode,b.tgtcode,AVG(e.ZJLXMainNetTur) AS net_avg "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"LEFT JOIN `{args.database}`.`hsj_stock_hq_ext` AS e "
            "ON e.mktcode=b.mktcode AND e.tgtcode=b.tgtcode AND e.bizdate=b.bizdate "
            f"WHERE b.bizdate IN ({date_5}) GROUP BY b.mktcode,b.tgtcode), "
            "t AS ("
            "SELECT b.mktcode,b.tgtcode,AVG(b.turnover) AS turnover_avg "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate IN ({date_5}) GROUP BY b.mktcode,b.tgtcode) "
            "SELECT a.mktcode,a.tgtcode,a.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS a "
            "INNER JOIN n ON n.mktcode=a.mktcode AND n.tgtcode=a.tgtcode "
            "INNER JOIN t ON t.mktcode=a.mktcode AND t.tgtcode=a.tgtcode "
            f"WHERE a.bizdate='{latest}' AND n.net_avg/NULLIF(t.turnover_avg,0)<20"
        ),
        "two_windows_with_latest_scalar": (
            "WITH a7 AS ("
            "SELECT b.mktcode,b.tgtcode,AVG(b.volume) AS volume_avg "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate IN ({date_7}) GROUP BY b.mktcode,b.tgtcode), "
            "m5 AS ("
            "SELECT b.mktcode,b.tgtcode,MIN(b.volume) AS volume_min "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate IN ({date_5}) GROUP BY b.mktcode,b.tgtcode) "
            "SELECT q.mktcode,q.tgtcode,q.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS q "
            "INNER JOIN a7 ON a7.mktcode=q.mktcode AND a7.tgtcode=q.tgtcode "
            "INNER JOIN m5 ON m5.mktcode=q.mktcode AND m5.tgtcode=q.tgtcode "
            f"WHERE q.bizdate='{latest}' AND a7.volume_avg=m5.volume_min "
            "AND ((q.lastPx-q.preClosePx)*100.0/NULLIF(q.preClosePx,0))>2"
        ),
        "nonempty_two_window_comparison": (
            "WITH a7 AS ("
            "SELECT b.mktcode,b.tgtcode,AVG(b.volume) AS volume_avg "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate IN ({date_7}) GROUP BY b.mktcode,b.tgtcode), "
            "m5 AS ("
            "SELECT b.mktcode,b.tgtcode,MIN(b.volume) AS volume_min "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate IN ({date_5}) GROUP BY b.mktcode,b.tgtcode) "
            "SELECT q.mktcode,q.tgtcode,q.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS q "
            "INNER JOIN a7 ON a7.mktcode=q.mktcode AND a7.tgtcode=q.tgtcode "
            "INNER JOIN m5 ON m5.mktcode=q.mktcode AND m5.tgtcode=q.tgtcode "
            f"WHERE q.bizdate='{latest}' AND a7.volume_avg>m5.volume_min"
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
        set_based = (
            " AS aggregate_0" in generated_sql
            and "WHERE (SELECT AVG(" not in generated_sql
            and "WHERE (SELECT MIN(" not in generated_sql
            and "WHERE (SELECT MAX(" not in generated_sql
            and "WHERE (SELECT SUM(" not in generated_sql
        )
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
                "set_based": set_based,
                "safe_division": "/" not in generated_sql or "NULLIF(" in generated_sql,
                "explain_sha256": hashlib.sha256(explain.encode("utf-8")).hexdigest(),
                "explain_excerpt": explain[:4000],
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": _query_rows(args, "SELECT VERSION()")[0][0],
        "basic_row_count": int(
            _query_rows(
                args,
                f"SELECT COUNT(*) FROM `{args.database}`.`hsj_stock_hq_basic`",
            )[0][0]
        ),
        "latest_session": latest,
        "repeats": args.repeats,
        "status": "PASS"
        if all(item["matched"] and item["set_based"] and item["safe_division"] for item in results)
        else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "set_based": sum(item["set_based"] for item in results),
        "safe_division": sum(item["safe_division"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _sql_literals(values) -> str:
    return ",".join(f"'{value}'" for value in values)


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
        "# Phase 16 命名组合聚合真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 基础行情表：`{report['basic_row_count']}` 行",
        f"- 完整行集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 集合式命名度量计划：`{report['set_based']}/{report['total']}`",
        f"- 安全除零：`{report['safe_division']}/{report['total']}`",
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
            "> 每个 reference SQL 都独立声明交易日集合、GROUP BY 度量关系和稳定键 Join；编译器 SQL 由 PhysicalAggregateGroup/PhysicalAggregateRef 经 SQLGlot AST 生成。旧路径曾静默忽略的增长、时序聚合和 rank 聚合不计入成功，继续返回专属诊断。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
