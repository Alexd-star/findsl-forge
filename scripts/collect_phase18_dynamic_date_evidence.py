from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

from findsl.official.pipeline import compile_official


CASES = (
    {"name": "current_month", "date": "本月", "resolver": "current_month"},
    {"name": "previous_week", "date": "上周", "resolver": "previous_week"},
    {"name": "previous_year", "date": "去年", "resolver": "previous_year"},
    {"name": "recent_two_months", "date": "近两个月", "resolver": "recent_two_months"},
    {"name": "current_quarter", "date": "本季度", "resolver": "current_quarter"},
    {"name": "anchor_month_day", "date": "3月2号", "resolver": "anchor_month_day"},
    {"name": "three_sessions_before_week", "date": "本周的前3天", "resolver": "before_week"},
    {"name": "five_sessions_after_date", "date": "2024年3月10号的后5日", "resolver": "after_date"},
    {"name": "preceding_session_slice", "date": "最近三天的前3日", "resolver": "preceding_slice"},
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Phase 18 dynamic date evidence on a real Doris snapshot"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase18_dynamic_date_doris.json")
    parser.add_argument("--report-output", default="reports/phase18_dynamic_date_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    trading_dates = [
        date.fromisoformat(row[0])
        for row in _query_rows(
            args,
            f"SELECT bizdate FROM `{args.database}`.`hsj_stock_hq_basic` "
            "GROUP BY bizdate ORDER BY bizdate",
        )
    ]
    if not trading_dates:
        raise RuntimeError("official basic table has no trading dates")
    anchor = trading_dates[-1]
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
        resolved = _resolve_dates(case["resolver"], anchor, trading_dates)
        if not resolved:
            raise RuntimeError(f"case {case['name']} resolved to an empty trading-date set")
        source = (
            f"indicator('沪', '', '成交量', '{case['date']}', '', '', '') "
            "> 100000000"
        )
        explicit_dates = ",".join(f"'{item.isoformat()}'" for item in resolved)
        reference_sql = (
            "SELECT b.mktcode,b.tgtcode,b.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.mktcode=1 AND b.bizdate IN ({explicit_dates}) "
            "AND b.volume>100000000"
        )
        generated_sql = compile_official(source).backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, reference_sql)}
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {tuple(row[:3]) for row in _query_rows(args, generated_sql)}
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join("\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated_sql}"))
        results.append(
            {
                "name": case["name"],
                "source": source,
                "resolved_start": resolved[0].isoformat(),
                "resolved_end": resolved[-1].isoformat(),
                "resolved_session_count": len(resolved),
                "resolved_dates_sha256": _date_hash(resolved),
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
                "explain_sha256": hashlib.sha256(explain.encode("utf-8")).hexdigest(),
                "explain_excerpt": "\n".join(explain.splitlines()[:80]),
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": _query_rows(args, "SELECT VERSION()")[0][0],
        "latest_data_date": anchor.isoformat(),
        "trading_date_count": len(trading_dates),
        "repeats": args.repeats,
        "status": "PASS" if all(item["matched"] for item in results) else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _resolve_dates(kind: str, anchor: date, calendar: list[date]) -> list[date]:
    if kind == "current_month":
        start, end = date(anchor.year, anchor.month, 1), anchor
    elif kind == "previous_week":
        current_monday = anchor - timedelta(days=anchor.weekday())
        start, end = current_monday - timedelta(days=7), current_monday - timedelta(days=1)
    elif kind == "previous_year":
        start, end = date(anchor.year - 1, 1, 1), date(anchor.year - 1, 12, 31)
    elif kind == "recent_two_months":
        start, end = _add_months(anchor, -2) + timedelta(days=1), anchor
    elif kind == "current_quarter":
        start_month = ((anchor.month - 1) // 3) * 3 + 1
        start, end = date(anchor.year, start_month, 1), anchor
    elif kind == "anchor_month_day":
        start = end = date(anchor.year, 3, 2)
    elif kind == "before_week":
        boundary = anchor - timedelta(days=anchor.weekday())
        return list(reversed([item for item in reversed(calendar) if item < boundary][:3]))
    elif kind == "after_date":
        boundary = date(2024, 3, 10)
        return [item for item in calendar if item > boundary][:5]
    elif kind == "preceding_slice":
        return calendar[-6:-3]
    else:
        raise ValueError(f"unsupported evidence date resolver: {kind}")
    return [item for item in calendar if start <= item <= end]


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


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


def _date_hash(values: list[date]) -> str:
    return hashlib.sha256("\n".join(item.isoformat() for item in values).encode("utf-8")).hexdigest()


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
        "# Phase 18 动态日期真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 最新数据日期：`{report['latest_data_date']}`",
        f"- Doris 交易日数量：`{report['trading_date_count']}`",
        f"- 完整行集哈希一致：`{report['matched']}/{report['total']}`",
        "",
        "| 场景 | 解析起点 | 解析终点 | 交易日数 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |",
        "|---|---|---|---:|---:|---:|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['resolved_start']} | {item['resolved_end']} | "
            f"{item['resolved_session_count']} | {item['expected_count']} | "
            f"{item['actual_count']} | {'是' if item['matched'] else '否'} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> 参考路径先从 Doris 原始 `bizdate` 去重序列独立解析显式日期集合，再执行只含常量日期列表的 reference SQL。生成路径来自 Domain IR、Physical IR 与 SQLGlot 后端。两条路径比较完整 `(mktcode,tgtcode,bizdate)` 行集，而不是只比较 COUNT。",
            "",
            "> `日/天/交易日` 仍按交易所会话集合处理；周、月、季度、年按自然周期处理。滚动两个月采用旧合同的 `anchor-2 MONTH+1 DAY` 左闭边界。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
