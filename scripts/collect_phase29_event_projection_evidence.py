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
        description="Collect real-Doris evidence for generalized temporal events"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--json-output", default="reports/phase29_event_projection_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase29_event_projection_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    price = "b.lastPx / 10000.0"
    partition = "PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate"

    position_stats = (
        "SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price} AS value,"
        f"MIN({price}) OVER({partition} ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS low_value,"
        f"MAX({price}) OVER({partition} ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS high_value "
        f"FROM {basic} b"
    )
    position_rows = (
        "SELECT mktcode,tgtcode,bizdate,"
        "value>low_value AND value<high_value AND "
        "(value-low_value)/NULLIF(high_value-low_value,0)<=0.25 AS matched "
        f"FROM ({position_stats}) position_stats"
    )
    low_stats = (
        "SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"{price} AS value,MIN({price}) OVER({partition} "
        "ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS low_value "
        f"FROM {basic} b"
    )
    low_rows = (
        "SELECT mktcode,tgtcode,bizdate,value<=low_value AS matched "
        f"FROM ({low_stats}) low_stats"
    )
    close_rows = (
        "SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"ABS({price}-t.ma5)/NULLIF(GREATEST(ABS({price}),ABS(t.ma5)),0)<=0.03 AS matched "
        f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
        "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate"
    )
    reset_rows = (
        "SELECT b.mktcode,b.tgtcode,b.bizdate,"
        f"ABS({price}-t.ma20)/NULLIF(ABS(t.ma20),0)<=0.02 "
        f"AND {price}>=t.ma20*0.995 AS matched "
        f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
        "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate"
    )

    cases = (
        {
            "name": "consecutive_historical_low_position",
            "source": "position('', '', '', '历史', '近20日', '', '', 'CONS>1') = '低'",
            "event_kind": "PhysicalPosition",
            "reference": _consecutive_reference(
                basic, position_rows, ">", 1, latest
            ),
            "required_sql": (
                "PhysicalPosition",
                "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
                "MAX(`runs`.`run_length`)",
            ),
        },
        {
            "name": "repeated_twenty_session_low",
            "source": "record_low('', '', '', '20日', '近20日', '', '', 'EXIST>=2日') = True",
            "event_kind": "PhysicalExtreme",
            "reference": _exist_reference(
                basic, low_rows, ">=", 2, latest
            ),
            "required_sql": (
                "PhysicalExtreme",
                "ROWS BETWEEN 19 PRECEDING AND CURRENT ROW",
                "`temporal_metrics`.`metric_value` >= 2",
            ),
        },
        {
            "name": "three_session_price_ma5_convergence",
            "source": "close_together('', '', '', '5日均线', '近20日', '', 'CONS=3日') = True",
            "event_kind": "PhysicalPattern",
            "reference": _consecutive_reference(
                basic, close_rows, ">=", 3, latest
            ),
            "required_sql": (
                "PhysicalPattern",
                "GREATEST(",
                "MAX(`runs`.`run_length`)",
            ),
        },
        {
            "name": "repeated_price_reset_to_ma20",
            "source": "reset('', '', '', '20日均线', '近20日', '', 'EXIST>=2日') = True",
            "event_kind": "PhysicalPattern",
            "reference": _exist_reference(
                basic, reset_rows, ">=", 2, latest
            ),
            "required_sql": (
                "PhysicalPattern",
                "<= 0.02",
                "* 0.995",
            ),
        },
    )

    results = []
    for case in cases:
        compiled = compile_official(case["source"])
        payload = compiled.to_dict()
        generated = payload["backend"]["sql"]
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
        physical_text = json.dumps(
            payload["physical"]["plan"], ensure_ascii=False, sort_keys=True
        )
        structural = (
            '"kind": "PhysicalEventProjection"' in physical_text
            and f'"kind": "{case["event_kind"]}"' in physical_text
            and all(
                token in physical_text or token in generated
                for token in case["required_sql"]
            )
        )
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": payload["physical"]["selected_strategy"],
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
        "performance_target_ms": 10_000,
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "non_empty": sum(item["non_empty"] for item in results),
        "structural_contracts": sum(item["structural_contract"] for item in results),
        "under_performance_target": sum(
            item["p95_ms"] < 10_000 for item in results
        ),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _consecutive_reference(
    basic: str,
    feature_rows: str,
    comparator: str,
    threshold: int,
    latest: str,
) -> str:
    return (
        f"WITH feature_rows AS ({feature_rows}), ranked_rows AS ("
        "SELECT mktcode,tgtcode,bizdate,matched,ROW_NUMBER() OVER("
        "PARTITION BY mktcode,tgtcode ORDER BY bizdate DESC) AS lookback_row "
        "FROM feature_rows), selected_rows AS ("
        "SELECT mktcode,tgtcode,bizdate,matched FROM ranked_rows "
        "WHERE lookback_row<=20), sequenced AS ("
        "SELECT mktcode,tgtcode,bizdate,matched,ROW_NUMBER() OVER("
        "PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS all_seq FROM selected_rows), "
        "matched_rows AS (SELECT mktcode,tgtcode,bizdate,all_seq,ROW_NUMBER() OVER("
        "PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS matched_seq FROM sequenced "
        "WHERE matched=TRUE), runs AS (SELECT mktcode,tgtcode,all_seq-matched_seq AS run_id,"
        "COUNT(*) AS run_length FROM matched_rows GROUP BY mktcode,tgtcode,all_seq-matched_seq), "
        "qualified AS (SELECT mktcode,tgtcode FROM runs GROUP BY mktcode,tgtcode "
        f"HAVING MAX(run_length){comparator}{threshold}) "
        f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN qualified q "
        "ON q.mktcode=b.mktcode AND q.tgtcode=b.tgtcode "
        f"WHERE b.bizdate='{latest}'"
    )


def _exist_reference(
    basic: str,
    feature_rows: str,
    comparator: str,
    threshold: int,
    latest: str,
) -> str:
    return (
        f"WITH feature_rows AS ({feature_rows}), ranked_rows AS ("
        "SELECT mktcode,tgtcode,bizdate,matched,ROW_NUMBER() OVER("
        "PARTITION BY mktcode,tgtcode ORDER BY bizdate DESC) AS lookback_row "
        "FROM feature_rows), qualified AS ("
        "SELECT mktcode,tgtcode FROM ranked_rows "
        "WHERE lookback_row<=20 GROUP BY mktcode,tgtcode "
        f"HAVING SUM(CASE WHEN matched THEN 1 ELSE 0 END){comparator}{threshold}) "
        f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} b JOIN qualified q "
        "ON q.mktcode=b.mktcode AND q.tgtcode=b.tgtcode "
        f"WHERE b.bizdate='{latest}'"
    )


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
        "# Phase 29 泛化事件投影 Doris 证据",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 最新数据日：`{report['latest_data_date']}`",
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
