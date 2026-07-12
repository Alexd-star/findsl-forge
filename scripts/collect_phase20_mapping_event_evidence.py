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
        description="Collect Phase 20 grounded mapping and window-event evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output", default="reports/phase20_mapping_event_doris.json")
    parser.add_argument("--report-output", default="reports/phase20_mapping_event_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    ext = f"`{args.database}`.`hsj_stock_hq_ext`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    quoted_latest = f"'{latest}'"
    cases = (
        {
            "name": "circulating_market_value",
            "source": "indicator('', '', '流通市值', '今日', '', '', '') > 5000000000",
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {basic} "
                f"WHERE bizdate={quoted_latest} AND lastPx/10000.0*listedShare>5000000000"
            ),
        },
        {
            "name": "order_imbalance_ratio",
            "source": "indicator('', '', '委比', '今日', '', '', '') > 10",
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {basic} WHERE bizdate={quoted_latest} "
                "AND (commissionBuy-commissionSale)*100.0/NULLIF(commissionBuy+commissionSale,0)>10"
            ),
        },
        {
            "name": "technical_boolean_composition",
            "source": (
                "indicator('', '', '放量', '今日', '', '', '') = True and "
                "indicator('', '', '均线多头排列', '今日', '', '', '') = True"
            ),
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {technical} "
                f"WHERE bizdate={quoted_latest} AND volume_breakout=TRUE AND ma_bullish=TRUE"
            ),
        },
        {
            "name": "main_buy_percentage",
            "source": "indicator('', '', '主力买入占比', '今日', '', '', '') > 50%",
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {ext} "
                f"WHERE bizdate={quoted_latest} AND ZJLXMainBuyCntPer/10000.0>50"
            ),
        },
        {
            "name": "limit_break_event",
            "source": "indicator('', '', '涨停炸板', '今日', '', '', '') = True",
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {ext} WHERE bizdate={quoted_latest} "
                "AND (COALESCE(lmtUpNum,0)>0 OR COALESCE(boardBreaks,0)>0)"
            ),
        },
        {
            "name": "technical_cross_above",
            "source": "cross_above('', '', '5日均线', '20日均线', '今日', '', '') = True",
            "reference": (
                "WITH w AS (SELECT mktcode,tgtcode,bizdate,ma5,ma20,"
                "LAG(ma5) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS p5,"
                "LAG(ma20) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS p20 "
                f"FROM {technical}) SELECT mktcode,tgtcode,bizdate FROM w "
                f"WHERE bizdate={quoted_latest} AND ma5>ma20 AND p5<=p20"
            ),
        },
        {
            "name": "cross_resource_cross_down",
            "source": "cross_down('', '', '最新价', '30日均线', '今日', '', '') = True",
            "reference": (
                "WITH w AS (SELECT b.mktcode,b.tgtcode,b.bizdate,b.lastPx/10000.0 AS px,t.ma30,"
                "LAG(b.lastPx/10000.0) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate) AS ppx,"
                "LAG(t.ma30) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate) AS pma "
                f"FROM {basic} AS b LEFT JOIN {technical} AS t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate) "
                "SELECT mktcode,tgtcode,bizdate FROM w "
                f"WHERE bizdate={quoted_latest} AND px<ma30 AND ppx>=pma"
            ),
        },
        {
            "name": "record_high_60_sessions",
            "source": "record_high('', '', '最高价', '60日', '今日', '', '', '') = True",
            "reference": (
                "WITH w AS (SELECT mktcode,tgtcode,bizdate,highPx/10000.0 AS px,"
                "MAX(highPx/10000.0) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                f"ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS extreme FROM {basic}) "
                "SELECT mktcode,tgtcode,bizdate FROM w "
                f"WHERE bizdate={quoted_latest} AND px>=extreme"
            ),
        },
        {
            "name": "record_low_history",
            "source": "record_low('', '', '最低价', '历史', '今日', '', '', '') = True",
            "reference": (
                "WITH w AS (SELECT mktcode,tgtcode,bizdate,lowPx/10000.0 AS px,"
                "MIN(lowPx/10000.0) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                f"ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS extreme FROM {basic}) "
                "SELECT mktcode,tgtcode,bizdate FROM w "
                f"WHERE bizdate={quoted_latest} AND px<=extreme"
            ),
        },
        {
            "name": "event_with_scalar_projection",
            "source": (
                "cross_above('', '', '5日均线', '20日均线', '今日', '', '') = True and "
                "indicator('', '', '成交量', '今日', '', '', '') > 0"
            ),
            "reference": (
                "WITH w AS (SELECT b.mktcode,b.tgtcode,b.bizdate,b.volume,t.ma5,t.ma20,"
                "LAG(t.ma5) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate) AS p5,"
                "LAG(t.ma20) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate) AS p20 "
                f"FROM {basic} AS b LEFT JOIN {technical} AS t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate) "
                "SELECT mktcode,tgtcode,bizdate FROM w "
                f"WHERE bizdate={quoted_latest} AND ma5>ma20 AND p5<=p20 AND volume>0"
            ),
        },
        {
            "name": "close_together_pattern",
            "source": "close_together('', '', '5日均线', '20日均线', '今日', '', '') = True",
            "reference": (
                f"SELECT mktcode,tgtcode,bizdate FROM {technical} WHERE bizdate={quoted_latest} "
                "AND ABS(ma5-ma20)/NULLIF(GREATEST(ABS(ma5),ABS(ma20)),0)<=0.03"
            ),
        },
        {
            "name": "reset_pattern",
            "source": "reset('', '', '最新价', '20日均线', '今日', '', '') = True",
            "reference": (
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} AS b "
                f"LEFT JOIN {technical} AS t ON t.mktcode=b.mktcode AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate "
                f"WHERE b.bizdate={quoted_latest} AND ABS(b.lastPx/10000.0-t.ma20)/NULLIF(ABS(t.ma20),0)<=0.02 "
                "AND b.lastPx/10000.0>=t.ma20*0.995"
            ),
        },
        {
            "name": "position_10_sessions",
            "source": "position('', '', '最新价', '10日', '今日', '', '', '') = '最高'",
            "reference": (
                "WITH w AS (SELECT mktcode,tgtcode,bizdate,lastPx/10000.0 AS px,"
                "MIN(lastPx/10000.0) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                "ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS lo,"
                "MAX(lastPx/10000.0) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                f"ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS hi FROM {basic}) "
                "SELECT mktcode,tgtcode,bizdate FROM w "
                f"WHERE bizdate={quoted_latest} AND CASE "
                "WHEN px IS NULL OR lo IS NULL OR hi IS NULL THEN NULL "
                "WHEN px<=lo THEN '最低' WHEN px>=hi THEN '最高' "
                "WHEN (px-lo)/NULLIF(hi-lo,0)<=0.25 THEN '低' "
                "WHEN (px-lo)/NULLIF(hi-lo,0)>=0.75 THEN '高' "
                "ELSE '中' END='最高'"
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
        explain = "\n".join("\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated}"))
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
        "# Phase 20 受控映射与窗口事件真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 最新交易日：`{report['latest_data_date']}`",
        f"- 完整结果集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 非空结果：`{report['non_empty']}/{report['total']}`",
        f"- 每条生成 SQL 重复执行：`{report['repeats']}` 次",
        "",
        "| 用例 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |",
        "|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['name']}` | {item['expected_count']} | {item['actual_count']} | "
            f"{'PASS' if item['matched'] else 'FAIL'} | {'yes' if item['non_empty'] else 'no'} | {item['p95_ms']:.4f} |"
        )
    lines.extend(
        [
            "",
            "每个用例均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256 和 EXPLAIN 摘要。",
            "空结果不会自动判错，但会在表格中单独标识，避免把两个空集合的相等误写成强正确性证据。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
