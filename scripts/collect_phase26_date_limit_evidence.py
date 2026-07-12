from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Phase 26 typed date-algebra and open-limit Doris evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--json-output", default="reports/phase26_date_limit_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase26_date_limit_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    anchor_month_start = f"DATE_TRUNC('{latest}', 'MONTH')"
    anchor_ninth = f"DATE_ADD({anchor_month_start}, INTERVAL '8' DAY)"
    anchor_march_ninth = (
        f"DATE_ADD(DATE_ADD(DATE_TRUNC('{latest}', 'YEAR'), "
        "INTERVAL '2' MONTH), INTERVAL '8' DAY)"
    )
    recent_half_year_start = f"DATE_ADD(DATE_SUB('{latest}', INTERVAL '6' MONTH), INTERVAL '1' DAY)"
    recent_two_year_start = f"DATE_TRUNC(DATE_SUB('{latest}', INTERVAL '1' YEAR), 'YEAR')"
    cases = (
        {
            "name": "fixed_year_following_range",
            "source": (
                "indicator('', '', '成交量', '2012年的后4年', '', 'AVG', '') > 0"
            ),
            "reference": (
                "WITH qualified AS (SELECT mktcode,tgtcode FROM "
                f"{basic} WHERE bizdate>='2013-01-01' AND bizdate<='2016-12-31' "
                "GROUP BY mktcode,tgtcode HAVING AVG(volume)>0) "
                "SELECT b.mktcode,b.tgtcode,b.bizdate FROM "
                f"{basic} b JOIN qualified q ON q.mktcode=b.mktcode AND "
                f"q.tgtcode=b.tgtcode WHERE b.bizdate='{latest}'"
            ),
        },
        {
            "name": "session_before_anchor_day",
            "source": "indicator('', '', '成交量', '9号的前1日', '', '', '') > 0",
            "reference": (
                "WITH target AS (SELECT MAX(bizdate) AS bizdate FROM "
                f"{basic} WHERE bizdate<{anchor_ninth}) SELECT b.mktcode,b.tgtcode,b.bizdate "
                f"FROM {basic} b JOIN target d ON d.bizdate=b.bizdate WHERE b.volume>0"
            ),
        },
        {
            "name": "sessions_after_anchor_day_every",
            "source": (
                "indicator('', '', '成交量', '3月9号的后3日', '', '', 'CONS=每日') > 0"
            ),
            "reference": (
                "WITH dates AS (SELECT bizdate FROM "
                f"{basic} WHERE bizdate>{anchor_march_ninth} GROUP BY bizdate "
                "ORDER BY bizdate ASC LIMIT 3), qualified AS (SELECT b.mktcode,b.tgtcode "
                f"FROM {basic} b JOIN dates d ON d.bizdate=b.bizdate GROUP BY "
                "b.mktcode,b.tgtcode HAVING COUNT(*)>0 AND SUM(CASE WHEN b.volume>0 "
                "THEN 1 ELSE 0 END)=COUNT(*)) SELECT b.mktcode,b.tgtcode,b.bizdate "
                f"FROM {basic} b JOIN qualified q ON q.mktcode=b.mktcode AND "
                f"q.tgtcode=b.tgtcode WHERE b.bizdate='{latest}'"
            ),
        },
        {
            "name": "recent_half_year_aggregate",
            "source": "indicator('', '', '成交量', '近半年', '', 'AVG', '') > 0",
            "reference": (
                "WITH qualified AS (SELECT mktcode,tgtcode FROM "
                f"{basic} WHERE bizdate>={recent_half_year_start} AND bizdate<='{latest}' "
                "GROUP BY mktcode,tgtcode HAVING AVG(volume)>0) "
                "SELECT b.mktcode,b.tgtcode,b.bizdate FROM "
                f"{basic} b JOIN qualified q ON q.mktcode=b.mktcode AND "
                f"q.tgtcode=b.tgtcode WHERE b.bizdate='{latest}'"
            ),
        },
        {
            "name": "fractional_year_to_six_month_buckets",
            "source": (
                "indicator('', '', '成交量', '近两年', '', 'SUM', 'CONS=0.5年') > 0"
            ),
            "reference": (
                "WITH monthly AS (SELECT mktcode,tgtcode,DATE_TRUNC(bizdate,'MONTH') AS bucket,"
                "YEAR(DATE_TRUNC(bizdate,'MONTH'))*12+MONTH(DATE_TRUNC(bizdate,'MONTH')) "
                f"AS ordinal,SUM(volume) AS metric FROM {basic} WHERE bizdate>={recent_two_year_start} "
                f"AND bizdate<='{latest}' GROUP BY mktcode,tgtcode,DATE_TRUNC(bizdate,'MONTH'),"
                "YEAR(DATE_TRUNC(bizdate,'MONTH'))*12+MONTH(DATE_TRUNC(bizdate,'MONTH'))), "
                "matched AS (SELECT mktcode,tgtcode,ordinal,ordinal-ROW_NUMBER() OVER("
                "PARTITION BY mktcode,tgtcode ORDER BY ordinal) AS island FROM monthly "
                "WHERE metric>0), qualified AS (SELECT mktcode,tgtcode FROM matched "
                "GROUP BY mktcode,tgtcode,island HAVING COUNT(*)>=6) "
                "SELECT DISTINCT b.mktcode,b.tgtcode,b.bizdate FROM "
                f"{basic} b JOIN qualified q ON q.mktcode=b.mktcode AND "
                f"q.tgtcode=b.tgtcode WHERE b.bizdate='{latest}'"
            ),
        },
        {
            "name": "deterministic_open_ended_limit",
            "source": (
                "indicator('', '', '成交量', '今日', '', '', '') > 0 limit 7,-1"
            ),
            "reference": (
                "SELECT mktcode,tgtcode,bizdate FROM "
                f"{basic} WHERE bizdate='{latest}' AND volume>0 "
                "ORDER BY mktcode,tgtcode,bizdate LIMIT 9223372036854775800 OFFSET 7"
            ),
        },
    )

    results = []
    for case in cases:
        compiled = compile_official(case["source"])
        generated = compiled.backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, case["reference"])}
        actual = set()
        elapsed = []
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {tuple(row[:3]) for row in _query_rows(args, generated)}
            elapsed.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join(
            "\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated}")
        )
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": compiled.physical.get("selected_strategy"),
                "generated_sql": generated,
                "reference_sql": case["reference"],
                "expected_count": len(expected),
                "actual_count": len(actual),
                "expected_sha256": _row_hash(expected),
                "actual_sha256": _row_hash(actual),
                "matched": expected == actual,
                "non_empty": bool(actual),
                "missing_sample": sorted(expected - actual)[:10],
                "extra_sample": sorted(actual - expected)[:10],
                "elapsed_ms": elapsed,
                "p95_ms": _nearest_rank(elapsed, 0.95),
                "explain_sha256": hashlib.sha256(explain.encode("utf-8")).hexdigest(),
                "explain_excerpt": "\n".join(explain.splitlines()[:80]),
            }
        )

    passed = all(item["matched"] and item["non_empty"] for item in results)
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "latest_data_date": latest,
        "repeats": args.repeats,
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "non_empty": sum(item["non_empty"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _query_rows(args, sql: str):
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
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Phase 26 日期代数与开放分页真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 最新交易日：`{report['latest_data_date']}`",
        f"- 完整结果集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 非空结果：`{report['non_empty']}/{report['total']}`",
        "",
        "| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |",
        "|---|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['name']}` | `{item['selected_strategy']}` | "
            f"{item['expected_count']} | {item['actual_count']} | "
            f"{'PASS' if item['matched'] else 'FAIL'} | "
            f"{'yes' if item['non_empty'] else 'no'} | {item['p95_ms']:.4f} |"
        )
    lines.extend(
        [
            "",
            "每组均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本和 EXPLAIN 摘要。",
            "参考 SQL 独立实现固定年份区间、锚点交易日、半年范围、六个月连续桶和稳定开放分页，不调用编译器 AST。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
