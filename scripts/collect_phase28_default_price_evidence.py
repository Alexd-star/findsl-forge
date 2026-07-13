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
        description="Collect real-Doris evidence for documented default-price events"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--json-output", default="reports/phase28_default_price_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase28_default_price_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    price = "b.lastPx / 10000.0"
    cases = (
        {
            "name": "price_crosses_above_ma20",
            "source": "cross_above('', '', '', '20日均线', '', '', '') = True",
            "reference": (
                "WITH event_rows AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
                f"{price}>t.ma20 AND LAG({price}) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate)"
                "<=LAG(t.ma20) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate) AS matched "
                f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate) "
                "SELECT mktcode,tgtcode,bizdate FROM event_rows "
                f"WHERE bizdate='{latest}' AND matched=TRUE"
            ),
            "required_sql": ("lastPx` / 10000.0 >", "LAG(", "event_rows"),
        },
        {
            "name": "price_does_not_cross_below_ma60",
            "source": "cross_down('', '', '', '60日均线', '', '', '') = False",
            "reference": (
                "WITH event_rows AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
                f"{price}<t.ma60 AND LAG({price}) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate)"
                ">=LAG(t.ma60) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate) AS matched "
                f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate) "
                "SELECT mktcode,tgtcode,bizdate FROM event_rows "
                f"WHERE bizdate='{latest}' AND matched=FALSE"
            ),
            "required_sql": ("event_absence_keys", "lastPx` / 10000.0 <", "LAG("),
        },
        {
            "name": "price_at_five_session_low",
            "source": "record_low('', '', '', '5日', '', '', '', '') = True",
            "reference": (
                "WITH event_rows AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
                f"{price} AS price,MIN({price}) OVER(PARTITION BY b.mktcode,b.tgtcode "
                f"ORDER BY b.bizdate ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS low5 FROM {basic} b) "
                "SELECT mktcode,tgtcode,bizdate FROM event_rows "
                f"WHERE bizdate='{latest}' AND price<=low5"
            ),
            "required_sql": ("MIN(", "ROWS BETWEEN 4 PRECEDING AND CURRENT ROW"),
        },
        {
            "name": "price_in_low_historical_quartile",
            "source": "position('', '', '', '历史', '', '', '', '') = '低'",
            "reference": (
                "WITH event_rows AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
                f"{price} AS price,MIN({price}) OVER(PARTITION BY b.mktcode,b.tgtcode "
                "ORDER BY b.bizdate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS low_all,"
                f"MAX({price}) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate "
                f"ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS high_all FROM {basic} b) "
                "SELECT mktcode,tgtcode,bizdate FROM event_rows "
                f"WHERE bizdate='{latest}' AND price>low_all AND price<high_all "
                "AND (price-low_all)/NULLIF(high_all-low_all,0)<=0.25"
            ),
            "required_sql": (
                "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
                "ELSE '中' END",
            ),
        },
        {
            "name": "price_close_to_ma20",
            "source": "close_together('', '', '', '20日均线', '', '', '') = True",
            "reference": (
                "SELECT b.mktcode,b.tgtcode,b.bizdate "
                f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate "
                f"WHERE b.bizdate='{latest}' AND ABS({price}-t.ma20)/"
                f"NULLIF(GREATEST(ABS({price}),ABS(t.ma20)),0)<=0.03"
            ),
            "required_sql": ("GREATEST(", "<= 0.03"),
        },
        {
            "name": "price_resets_to_ma5",
            "source": "reset('', '', '', '5日均线', '', '', '') = True",
            "reference": (
                "SELECT b.mktcode,b.tgtcode,b.bizdate "
                f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate "
                f"WHERE b.bizdate='{latest}' AND ABS({price}-t.ma5)/NULLIF(ABS(t.ma5),0)<=0.02 "
                f"AND {price}>=t.ma5*0.995"
            ),
            "required_sql": ("<= 0.02", "* 0.995"),
        },
    )

    results = []
    for case in cases:
        compiled = compile_official(case["source"])
        payload = compiled.to_dict()
        generated = payload["backend"]["sql"]
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
        logical_default = _logical_default_materialized(payload["logical"]["plan"])
        structural = logical_default and all(
            token in generated for token in case["required_sql"]
        )
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": payload["physical"]["selected_strategy"],
                "generated_sql": generated,
                "reference_sql": case["reference"],
                "required_sql": list(case["required_sql"]),
                "logical_default_materialized": logical_default,
                "structural_contract": structural,
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

    passed = all(
        item["matched"] and item["non_empty"] and item["structural_contract"]
        for item in results
    )
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "latest_data_date": latest,
        "repeats": args.repeats,
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "non_empty": sum(item["non_empty"] for item in results),
        "structural_contracts": sum(item["structural_contract"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _logical_default_materialized(plan) -> bool:
    default_slots = {
        "cross_above": "indicator_name_1",
        "cross_down": "indicator_name_1",
        "close_together": "indicator_name_1",
        "reset": "indicator_name_1",
        "record_high": "indicator_name",
        "record_low": "indicator_name",
        "position": "indicator_name",
    }
    for node in _walk_dicts(plan):
        name = node.get("name")
        if node.get("kind") != "CallExpr" or name not in default_slots:
            continue
        slots = node.get("binding", {}).get("slots", {})
        if slots.get(default_slots[name]) == "最新价":
            return True
    return False


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


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
        check=True,
    )
    return result.stdout.strip()


def _write_report(report, json_output: str, report_output: str) -> None:
    json_path = Path(json_output)
    report_path = Path(report_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Phase 28 默认价格事件 Doris 证据",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 最新数据日：`{report['latest_data_date']}`",
        f"- 状态：`{report['status']}`",
        f"- 完整行集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 非空结果：`{report['non_empty']}/{report['total']}`",
        f"- 结构合同通过：`{report['structural_contracts']}/{report['total']}`",
        "",
        "| 场景 | 策略 | 参考/实际行数 | P95(ms) | 哈希一致 | 非空 | 结构合同 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['selected_strategy']} | "
            f"{item['expected_count']}/{item['actual_count']} | {item['p95_ms']:.4f} | "
            f"{'PASS' if item['matched'] else 'FAIL'} | "
            f"{'PASS' if item['non_empty'] else 'FAIL'} | "
            f"{'PASS' if item['structural_contract'] else 'FAIL'} |"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
