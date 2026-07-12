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
    {
        "name": "chinese_year_2024",
        "date": "二四年",
        "start": "2024-01-01",
        "end": "2024-12-31",
    },
    {
        "name": "calendar_month_2024_08",
        "date": "2024年8月",
        "start": "2024-08-01",
        "end": "2024-08-31",
    },
    {
        "name": "calendar_day_2024_08_01",
        "date": "2024年8月1日",
        "start": "2024-08-01",
        "end": "2024-08-01",
    },
    {"name": "previous_trading_session", "date": "昨天", "offset": 1},
    {"name": "two_trading_sessions_ago", "date": "前天", "offset": 2},
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Phase 11 typed date evidence on a real Doris snapshot"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase11_date_doris.json")
    parser.add_argument("--report-output", default="reports/phase11_date_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    trading_dates = [
        row[0]
        for row in _query_rows(
            args,
            f"SELECT bizdate FROM `{args.database}`.`hsj_stock_hq_basic` "
            "GROUP BY bizdate ORDER BY bizdate DESC LIMIT 3",
        )
    ]
    if len(trading_dates) != 3:
        raise RuntimeError("official basic table has fewer than three trading dates")
    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    if not doris_versions:
        raise RuntimeError("SHOW FRONTENDS did not expose a Doris build version")

    results = []
    for case in CASES:
        source = (
            f"indicator('沪', '', '成交量', '{case['date']}', '', '', '') "
            "> 100000000"
        )
        if "offset" in case:
            start = end = trading_dates[case["offset"]]
        else:
            start, end = case["start"], case["end"]
        if start == end:
            date_predicate = f"b.bizdate='{start}'"
        else:
            date_predicate = f"b.bizdate>='{start}' AND b.bizdate<='{end}'"
        reference_sql = (
            "SELECT b.mktcode,b.tgtcode,b.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.mktcode=1 AND {date_predicate} AND b.volume>100000000"
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
                "name": case["name"],
                "source": source,
                "resolved_start": start,
                "resolved_end": end,
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
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": _query_rows(args, "SELECT VERSION()")[0][0],
        "latest_trading_dates": trading_dates,
        "repeats": args.repeats,
        "status": "PASS" if all(item["matched"] for item in results) else "FAIL",
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
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Phase 11 Typed Date IR 真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 最近三个交易日：`{', '.join(report['latest_trading_dates'])}`",
        f"- 行集哈希一致：`{report['matched']}/{report['total']}`",
        "",
        "| 场景 | 解析起点 | 解析终点 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['resolved_start']} | {item['resolved_end']} | "
            f"{item['expected_count']} | {item['actual_count']} | "
            f"{'是' if item['matched'] else '否'} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> 年、月、日边界由独立 reference SQL 使用显式日期常量校验；昨天和前天先从 Doris 原始交易日序列独立取值，再与编译器生成的 NthLatestValue 子查询比较完整结果行集。交易日偏移不使用自然日减法。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
