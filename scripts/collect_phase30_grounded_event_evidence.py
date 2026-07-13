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
        description="Collect Doris evidence for grounded event periods and scopes"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--json-output", default="reports/phase30_grounded_event_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase30_grounded_event_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    security = f"`{args.database}`.`hsj_stock_code_info`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    half_year_start = _query_rows(
        args,
        f"SELECT DATE_ADD(DATE_SUB('{latest}',INTERVAL 6 MONTH),INTERVAL 1 DAY)",
    )[0][0]
    fixed_date = f"{latest[:4]}-02-25"
    price = "b.lastPx/10000.0"
    partition = "PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate"

    low10 = (
        "WITH features AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price} AS value,MIN({price}) OVER({partition} ROWS BETWEEN 9 PRECEDING "
        f"AND CURRENT ROW) AS rolling_low FROM {basic} b) "
        "SELECT mktcode,tgtcode,bizdate FROM features "
        f"WHERE bizdate='{latest}' AND value<=rolling_low"
    )
    high_low20 = (
        "WITH features AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price} AS value,MIN({price}) OVER({partition} ROWS BETWEEN 19 PRECEDING "
        f"AND CURRENT ROW) AS rolling_low,MAX({price}) OVER({partition} ROWS BETWEEN "
        f"19 PRECEDING AND CURRENT ROW) AS rolling_high FROM {basic} b) "
        "SELECT mktcode,tgtcode,bizdate FROM features "
        f"WHERE bizdate='{latest}' AND (value<=rolling_low OR value>=rolling_high)"
    )
    scoped_cross = (
        "WITH events AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price}>t.ma60 AND LAG({price}) OVER({partition})<=LAG(t.ma60) OVER({partition}) "
        f"AS matched FROM {basic} b JOIN {security} s ON s.mktcode=b.mktcode "
        "AND s.tgtcode=b.tgtcode LEFT JOIN "
        f"{technical} t ON t.mktcode=b.mktcode AND t.tgtcode=b.tgtcode "
        "AND t.bizdate=b.bizdate WHERE s.name='上海电力'), qualified AS ("
        "SELECT mktcode,tgtcode FROM events GROUP BY mktcode,tgtcode "
        "HAVING SUM(CASE WHEN matched THEN 1 ELSE 0 END)>1) "
        f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN qualified q "
        "ON q.mktcode=b.mktcode AND q.tgtcode=b.tgtcode "
        f"WHERE b.bizdate='{latest}'"
    )
    support_pressure = (
        "WITH events AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price}>b.pressure/10000.0 AND LAG({price}) OVER({partition})"
        f"<=LAG(b.pressure/10000.0) OVER({partition}) AS crossed_up,"
        f"{price}<b.pressure/10000.0 AND LAG({price}) OVER({partition})"
        f">=LAG(b.pressure/10000.0) OVER({partition}) AS crossed_down FROM {basic} b),"
        " qualified AS (SELECT mktcode,tgtcode FROM events GROUP BY mktcode,tgtcode "
        "HAVING SUM(CASE WHEN crossed_up OR crossed_down THEN 1 ELSE 0 END)>0) "
        f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN qualified q "
        "ON q.mktcode=b.mktcode AND q.tgtcode=b.tgtcode "
        f"WHERE b.bizdate='{latest}' AND ABS({price}-b.support/10000.0)/"
        f"NULLIF(ABS(b.support/10000.0),0)<=0.02 AND {price}>="
        "(b.support/10000.0)*0.995"
    )
    unsealed = (
        f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b "
        f"WHERE b.bizdate='{fixed_date}' AND b.upSealPx>0 "
        "AND b.highPx>=b.upSealPx AND b.limitFlag<>1"
    )
    historical_low = (
        "WITH features AS (SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price} AS value,MIN({price}) OVER({partition} ROWS BETWEEN UNBOUNDED "
        f"PRECEDING AND CURRENT ROW) AS historical_low FROM {basic} b) "
        "SELECT mktcode,tgtcode,bizdate FROM features "
        f"WHERE bizdate>='{half_year_start}' AND bizdate<='{latest}' "
        "AND value<=historical_low"
    )

    cases = (
        {
            "name": "half_month_price_low",
            "source": "record_low('', '', '', '半个月', '', '', '', '') = True",
            "reference": low10,
            "required_sql": ("ROWS BETWEEN 9 PRECEDING AND CURRENT ROW",),
        },
        {
            "name": "previous_month_price_extreme",
            "source": "record_high('', '', '', '上个月', '', '', '', '') = True or record_low('', '', '', '上个月', '', '', '', '') = True",
            "reference": high_low20,
            "required_sql": ("ROWS BETWEEN 19 PRECEDING AND CURRENT ROW", " OR "),
        },
        {
            "name": "exact_security_repeated_crossing",
            "source": "cross_above('', '上海电力', '', '60日均线', '', '', 'EXIST>1') = True",
            "reference": scoped_cross,
            "required_sql": ("`official_security`.`name` = '上海电力'", "LAG("),
        },
        {
            "name": "support_reset_and_pressure_crossing",
            "source": "reset('', '', '', '支撑位', '今天', '', '') = True and (cross_above('', '', '', '压力位', '', '', 'EXIST>0') = True or cross_down('', '', '', '压力位', '', '', 'EXIST>0') = True)",
            "reference": support_pressure,
            "required_sql": ("`q`.`support` / 10000.0", "`q`.`pressure` / 10000.0"),
        },
        {
            "name": "unsealed_limit_event",
            "source": "indicator('', '', '涨停未封板', '2月25号', '', '', '') = True",
            "reference": unsealed,
            "required_sql": ("`q`.`upSealPx` > 0", "`q`.`limitFlag` <> 1"),
        },
        {
            "name": "half_year_historical_low",
            "source": "position('', '', '', '历史', '半年内', '', '', '') = '最低'",
            "reference": historical_low,
            "required_sql": ("INTERVAL '6' MONTH", "UNBOUNDED PRECEDING"),
        },
    )

    results = []
    for case in cases:
        compiled = compile_official(case["source"])
        generated = compiled.backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, case["reference"])}
        _query_rows(args, generated)
        actual = set()
        elapsed = []
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {tuple(row[:3]) for row in _query_rows(args, generated)}
            elapsed.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join(
            "\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated}")
        )
        structural = all(token in generated for token in case["required_sql"])
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": compiled.physical["selected_strategy"],
                "generated_sql": generated,
                "reference_sql": case["reference"],
                "required_sql": list(case["required_sql"]),
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
        item["matched"]
        and item["non_empty"]
        and item["structural_contract"]
        and item["p95_ms"] < 10_000
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
        "under_performance_target": sum(item["p95_ms"] < 10_000 for item in results),
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
        "# Phase 30 有据事件周期与范围 Doris 证据",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 状态：`{report['status']}`",
        f"- 完整行集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 非空结果：`{report['non_empty']}/{report['total']}`",
        f"- 结构合同通过：`{report['structural_contracts']}/{report['total']}`",
        f"- P95 低于 10 秒：`{report['under_performance_target']}/{report['total']}`",
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
