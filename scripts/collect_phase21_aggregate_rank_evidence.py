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
        description="Collect Phase 21 approximation, aggregate, and rank evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--json-output", default="reports/phase21_aggregate_rank_doris.json")
    parser.add_argument("--report-output", default="reports/phase21_aggregate_rank_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    latest_filter = f"a.bizdate='{latest}'"
    recent5 = (
        f"SELECT bizdate FROM {basic} GROUP BY bizdate ORDER BY bizdate DESC LIMIT 5"
    )
    recent10_rows = (
        "SELECT mktcode,tgtcode,bizdate,volume,"
        "ROW_NUMBER() OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate DESC) AS lookback_row "
        f"FROM {basic}"
    )
    latest_join = (
        f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM {basic} a JOIN qualified q "
        "ON q.mktcode=a.mktcode AND q.tgtcode=a.tgtcode "
        f"WHERE {latest_filter}"
    )
    growth_expr = (
        "(MAX_BY(volume,bizdate)-MIN_BY(volume,bizdate))*100/"
        "NULLIF(ABS(MIN_BY(volume,bizdate)),0)"
    )
    cases = (
        {
            "name": "configured_relative_approximation",
            "source": "indicator('', '', '最新价', '今日', '', '', '') ~= 10",
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {basic} WHERE bizdate='{latest}' "
                "AND ABS(lastPx/10000.0-10)<=GREATEST(0.01,0.01*"
                "GREATEST(ABS(lastPx/10000.0),ABS(10)))"
            ),
        },
        {
            "name": "five_session_growth_filter",
            "source": "indicator('', '', '成交量', '近5日', '', 'GROWTH_RISE', '') > 0",
            "reference": (
                "WITH metric AS (SELECT mktcode,tgtcode,"
                f"{growth_expr} AS value FROM {basic} WHERE bizdate IN ({recent5}) "
                "GROUP BY mktcode,tgtcode), qualified AS ("
                "SELECT mktcode,tgtcode FROM metric WHERE value>0) "
                + latest_join
            ),
        },
        {
            "name": "daily_growth_exist",
            "source": (
                "indicator('', '', '成交量', '近10个交易日内', '', "
                "'GROWTH_RISE', 'EXIST>0') > 50%"
            ),
            "reference": (
                f"WITH source AS ({recent10_rows}), eligible AS (SELECT * FROM source WHERE lookback_row<=10), "
                "daily AS (SELECT mktcode,tgtcode,bizdate,MAX(volume) AS value FROM eligible "
                "GROUP BY mktcode,tgtcode,bizdate), lagged AS (SELECT mktcode,tgtcode,bizdate,value,"
                "LAG(value) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS previous FROM daily), "
                "qualified AS (SELECT mktcode,tgtcode FROM lagged GROUP BY mktcode,tgtcode "
                "HAVING SUM(CASE WHEN (value-previous)*100/NULLIF(ABS(previous),0)>50 THEN 1 ELSE 0 END)>0) "
                + latest_join
            ),
        },
        {
            "name": "daily_max_consecutive",
            "source": "indicator('', '', '成交量', '近10个交易日', '', 'MAX', 'CONS>=3日') > 0",
            "reference": (
                f"WITH source AS ({recent10_rows}), eligible AS (SELECT * FROM source WHERE lookback_row<=10), "
                "daily AS (SELECT mktcode,tgtcode,bizdate,MAX(volume) AS value FROM eligible "
                "GROUP BY mktcode,tgtcode,bizdate), sequenced AS (SELECT *,"
                "ROW_NUMBER() OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS all_seq FROM daily), "
                "hits AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS hit_seq "
                "FROM sequenced WHERE value>0), runs AS (SELECT mktcode,tgtcode,all_seq-hit_seq AS grp,COUNT(*) AS n "
                "FROM hits GROUP BY mktcode,tgtcode,all_seq-hit_seq), qualified AS ("
                "SELECT mktcode,tgtcode FROM runs GROUP BY mktcode,tgtcode HAVING MAX(n)>=3) "
                + latest_join
            ),
        },
        {
            "name": "growth_rank_top10",
            "source": "rank('', '', '成交量', 'desc', '近5日', '', 'GROWTH_RISE', '') <= 10",
            "reference": (
                "WITH metric AS (SELECT mktcode,tgtcode,"
                f"{growth_expr} AS value FROM {basic} WHERE bizdate IN ({recent5}) "
                "GROUP BY mktcode,tgtcode), ranked AS (SELECT mktcode,tgtcode,"
                "ROW_NUMBER() OVER(ORDER BY value DESC,mktcode ASC,tgtcode ASC) AS rn FROM metric), "
                "qualified AS (SELECT mktcode,tgtcode FROM ranked WHERE rn<=10) "
                + latest_join
            ),
        },
        {
            "name": "daily_growth_temporal_rank",
            "source": (
                "rank('', '', '成交量', 'desc', '近10个交易日', '', "
                "'GROWTH_RISE', 'EXIST>0日') <= 20%"
            ),
            "reference": (
                f"WITH source AS ({recent10_rows}), eligible AS (SELECT * FROM source WHERE lookback_row<=10), "
                "daily AS (SELECT mktcode,tgtcode,bizdate,MAX(volume) AS value FROM eligible "
                "GROUP BY mktcode,tgtcode,bizdate), lagged AS (SELECT mktcode,tgtcode,bizdate,value,"
                "LAG(value) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS previous FROM daily), "
                "metric AS (SELECT mktcode,tgtcode,bizdate,(value-previous)*100/NULLIF(ABS(previous),0) AS value "
                "FROM lagged), ranked AS (SELECT mktcode,tgtcode,bizdate,"
                "ROW_NUMBER() OVER(PARTITION BY bizdate ORDER BY value DESC,mktcode ASC,tgtcode ASC) AS rn,"
                "COUNT(*) OVER(PARTITION BY bizdate) AS population FROM metric), qualified AS ("
                "SELECT mktcode,tgtcode FROM ranked GROUP BY mktcode,tgtcode "
                "HAVING SUM(CASE WHEN rn<=CEIL(population*20/100.0) THEN 1 ELSE 0 END)>0) "
                + latest_join
            ),
        },
    )

    results = []
    for case in cases:
        generated = compile_official(case["source"]).backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, case["reference"])}
        elapsed = []
        actual = set()
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

    passed = all(item["matched"] for item in results)
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
        "# Phase 21 近似、聚合与排名真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 最新交易日：`{report['latest_data_date']}`",
        f"- 完整结果集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 非空结果：`{report['non_empty']}/{report['total']}`",
        "",
        "| 用例 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |",
        "|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['name']}` | {item['expected_count']} | {item['actual_count']} | "
            f"{'PASS' if item['matched'] else 'FAIL'} | {'yes' if item['non_empty'] else 'no'} | "
            f"{item['p95_ms']:.4f} |"
        )
    lines.extend(
        [
            "",
            "每个用例保存生成 SQL、独立参考 SQL、完整结果集 SHA-256 和 EXPLAIN 摘要。",
            "参考 SQL 独立写出数学与集合语义，不复用编译器生成 AST。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
