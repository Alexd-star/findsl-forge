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
        description="Collect Phase 27 event-composition and temporal-event Doris evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--json-output", default="reports/phase27_event_semantics_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase27_event_semantics_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    previous = _query_rows(
        args,
        f"SELECT bizdate FROM {basic} GROUP BY bizdate ORDER BY bizdate DESC LIMIT 1 OFFSET 1",
    )[0][0]
    crossing_rows = (
        "SELECT mktcode,tgtcode,bizdate,"
        "ma3>ma30 AND LAG(ma3) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate)"
        "<=LAG(ma30) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS matched "
        f"FROM {technical}"
    )
    cases = (
        {
            "name": "bounded_crossing_existence",
            "source": "golden_cross('', '', '3日均线', '30日均线', '近一年', '', 'EXIST>0') = True",
            "reference": (
                f"WITH event_rows AS ({crossing_rows}), qualified AS ("
                "SELECT mktcode,tgtcode FROM event_rows "
                f"WHERE bizdate>=DATE_TRUNC('{latest}','YEAR') AND bizdate<='{latest}' "
                "GROUP BY mktcode,tgtcode HAVING SUM(CASE WHEN matched THEN 1 ELSE 0 END)>0) "
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN qualified q "
                "ON q.mktcode=b.mktcode AND q.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}'"
            ),
            "required_sql": ("LAG(", "temporal_metrics AS", "metric_value` > 0"),
        },
        {
            "name": "monthly_crossing_bucket",
            "source": "golden_cross('', '', '3日均线', '30日均线', '本月', '', 'CONS=每月') = True",
            "reference": (
                f"WITH event_rows AS ({crossing_rows}), monthly AS ("
                "SELECT mktcode,tgtcode,DATE_TRUNC(bizdate,'MONTH') AS bucket,"
                "MAX(CASE WHEN matched THEN 1 ELSE 0 END) AS matched FROM event_rows "
                f"WHERE bizdate>=DATE_TRUNC('{latest}','MONTH') AND bizdate<='{latest}' "
                "GROUP BY mktcode,tgtcode,DATE_TRUNC(bizdate,'MONTH')), qualified AS ("
                "SELECT mktcode,tgtcode FROM monthly GROUP BY mktcode,tgtcode "
                "HAVING SUM(matched)=COUNT(*)) "
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN qualified q "
                "ON q.mktcode=b.mktcode AND q.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}'"
            ),
            "required_sql": ("LAG(", "bucket_rows AS", "DATE_TRUNC("),
        },
        {
            "name": "cross_date_event_intersection",
            "source": (
                "record_high('', '', '最高价', '1日内', '今日', '', '', '') = True and "
                "record_high('', '', '最高价', '1日内', '昨日', '', '', '') = True"
            ),
            "reference": (
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN {basic} p "
                "ON p.mktcode=b.mktcode AND p.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}' AND p.bizdate='{previous}' "
                "AND b.highPx IS NOT NULL AND p.highPx IS NOT NULL"
            ),
            "required_sql": (
                " INTERSECT ",
                "ROWS BETWEEN CURRENT ROW AND CURRENT ROW",
                "OFFSET 1",
            ),
        },
        {
            "name": "eighty_session_extreme_with_latest_scalar",
            "source": (
                "record_high('', '', '收盘价', '80内', '三日内', '', '', '') = True and "
                "indicator('', '', '收盘价', '', '', '', '') < 10"
            ),
            "reference": (
                "WITH event_rows AS (SELECT mktcode,tgtcode,bizdate,closePx,"
                "MAX(closePx) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                f"ROWS BETWEEN 79 PRECEDING AND CURRENT ROW) AS rolling_high FROM {basic}), "
                "recent_events AS (SELECT DISTINCT mktcode,tgtcode FROM event_rows "
                f"WHERE closePx>=rolling_high AND bizdate IN (SELECT bizdate FROM {basic} "
                "GROUP BY bizdate ORDER BY bizdate DESC LIMIT 3)) "
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN recent_events e "
                "ON e.mktcode=b.mktcode AND e.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}' AND b.closePx/10000.0<10"
            ),
            "required_sql": (
                " INTERSECT ",
                "ROWS BETWEEN 79 PRECEDING AND CURRENT ROW",
                "q_latest",
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
        structural = all(token in generated for token in case["required_sql"])
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": compiled.physical.get("selected_strategy"),
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
        item["matched"] and item["non_empty"] and item["structural_contract"]
        for item in results
    )
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "latest_data_date": latest,
        "previous_data_date": previous,
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
        "# Phase 27 事件语义 Doris 证据",
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
