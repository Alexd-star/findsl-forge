from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from findsl.official.domain.temporal import (
    evaluate_calendar_bucket_matches,
    evaluate_temporal_matches,
    parse_temporal_quantifier,
)
from findsl.official.pipeline import compile_official


CASES = (
    {
        "name": "volume_recent_10_cons_3",
        "source": "indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') > 100",
        "branches": (("volume", 100, "CONS=3日", 10),),
    },
    {
        "name": "volume_recent_10_exist_5",
        "source": "indicator('', '', '成交量', '最近10日', '', '', 'EXIST>=5') > 100",
        "branches": (("volume", 100, "EXIST>=5", 10),),
    },
    {
        "name": "volume_this_5_exist",
        "source": "indicator('', '', '成交量', '这五天', '', '', 'EXIST>0') > 100",
        "branches": (("volume", 100, "EXIST>0", 5),),
    },
    {
        "name": "volume_this_5_every",
        "source": "indicator('', '', '成交量', '这五天', '', '', 'CONS=每日') > 100",
        "branches": (("volume", 100, "CONS=每日", 5),),
    },
    {
        "name": "volume_turnover_temporal_intersection",
        "source": (
            "indicator('', '', '成交量', '最近5日', '', '', 'EXIST>0') > 100 and "
            "indicator('', '', '成交额', '最近10日', '', '', 'CONS=3日') > 0"
        ),
        "operation": "intersect",
        "branches": (
            ("volume", 100, "EXIST>0", 5),
            ("turnover", 0, "CONS=3日", 10),
        ),
    },
    {
        "name": "volume_main_inflow_temporal_union",
        "source": (
            "indicator('', '', '成交量', '最近5日', '', '', 'EXIST>0') > 100 or "
            "indicator('', '', '主力净流入', '最近5日', '', '', 'EXIST>0') > 0"
        ),
        "operation": "union",
        "branches": (
            ("volume", 100, "EXIST>0", 5),
            ("main_inflow", 0, "EXIST>0", 5),
        ),
    },
)

BUCKET_CASES = (
    ("volume_two_year_every_year", "CONS=每年", "年"),
    ("volume_two_year_exist_2_months", "EXIST>=2月", "月"),
    ("volume_two_year_cons_3_quarters", "CONS=3季度", "季度"),
    ("volume_two_year_every_week", "CONS=每周", "周"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect independent Phase 9 temporal Doris evidence")
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output", default="reports/phase9_temporal_doris.json")
    parser.add_argument("--report-output", default="reports/phase9_temporal_doris.md")
    args = parser.parse_args()

    rows = _query_rows(args, _oracle_source_sql(args.database))
    protocol_version = _query_rows(args, "SELECT VERSION()")[0][0]
    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        {
            value
            for row in frontend_rows
            for value in row
            if value.lower().startswith("doris-")
        }
    )
    if not doris_versions:
        raise RuntimeError("SHOW FRONTENDS did not expose a Doris build version")
    official_row_count = int(
        _query_rows(
            args,
            f"SELECT COUNT(*) FROM `{args.database}`.`hsj_stock_hq_basic`",
        )[0][0]
    )
    latest_date = _query_rows(
        args,
        f"SELECT MAX(bizdate) FROM `{args.database}`.`hsj_stock_hq_basic`",
    )[0][0]
    latest_universe = {
        (row[0], row[1])
        for row in _query_rows(
            args,
            f"SELECT mktcode,tgtcode FROM `{args.database}`.`hsj_stock_hq_basic` WHERE bizdate='{latest_date}'",
        )
    }
    grouped = _group_records(rows)

    results = []
    for case in CASES:
        branch_sets = []
        for field, threshold, count_exp, lookback_sessions in case["branches"]:
            quantifier = parse_temporal_quantifier(count_exp)
            branch_sets.append(
                {
                    key
                    for key, records in grouped.items()
                    if key in latest_universe
                    and evaluate_temporal_matches(
                        [record[field] > threshold for record in records[-lookback_sessions:]],
                        quantifier,
                    )
                }
            )
        if case.get("operation") == "intersect":
            expected_stocks = set.intersection(*branch_sets)
        elif case.get("operation") == "union":
            expected_stocks = set.union(*branch_sets)
        else:
            expected_stocks = branch_sets[0]
        expected = {(market, code, latest_date) for market, code in expected_stocks}
        compiled = compile_official(case["source"])
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            output = _query_rows(args, compiled.backend["sql"])
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
            actual = {tuple(row[:3]) for row in output}
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "sql": compiled.backend["sql"],
                "expected_count": len(expected),
                "actual_count": len(actual),
                "expected_sha256": _row_hash(expected),
                "actual_sha256": _row_hash(actual),
                "matched": expected == actual,
                "missing_sample": sorted(expected - actual)[:10],
                "extra_sample": sorted(actual - expected)[:10],
                "elapsed_ms": timings,
                "p95_ms": max(timings),
            }
        )

    bucket_rows = _query_rows(args, _bucket_oracle_source_sql(args.database, latest_date))
    bucket_grouped = defaultdict(list)
    for market, code, bizdate, volume in bucket_rows:
        bucket_grouped[(market, code)].append((bizdate, _numeric(volume)))
    bucket_sample = set(bucket_grouped)
    for name, count_exp, unit in BUCKET_CASES:
        source = f"indicator('', '', '成交量', '两年内', '', '', '{count_exp}') > 100"
        quantifier = parse_temporal_quantifier(count_exp)
        expected_stocks = {
            key
            for key, records in bucket_grouped.items()
            if evaluate_calendar_bucket_matches(
                [(_bucket_ordinal(raw_date, unit), value > 100) for raw_date, value in records],
                quantifier,
            )
        }
        expected = {(market, code, latest_date) for market, code in expected_stocks}
        compiled = compile_official(source)
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            output = _query_rows(args, compiled.backend["sql"])
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
            actual = {
                tuple(row[:3])
                for row in output
                if (row[0], row[1]) in bucket_sample
            }
        results.append(
            {
                "name": name,
                "source": source,
                "sql": compiled.backend["sql"],
                "oracle_scope": "deterministic_latest_stock_sample",
                "oracle_stock_count": len(bucket_sample),
                "expected_count": len(expected),
                "actual_count": len(actual),
                "expected_sha256": _row_hash(expected),
                "actual_sha256": _row_hash(actual),
                "matched": expected == actual,
                "missing_sample": sorted(expected - actual)[:10],
                "extra_sample": sorted(actual - expected)[:10],
                "elapsed_ms": timings,
                "p95_ms": max(timings),
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": protocol_version,
        "official_basic_rows": official_row_count,
        "latest_date": latest_date,
        "oracle_rows": len(rows),
        "bucket_oracle_rows": len(bucket_rows),
        "bucket_oracle_stocks": len(bucket_sample),
        "latest_universe": len(latest_universe),
        "repeats": args.repeats,
        "status": "PASS" if all(item["matched"] for item in results) else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _oracle_source_sql(database: str) -> str:
    return (
        "WITH ranked_source AS ("
        "SELECT b.mktcode,b.tgtcode,b.bizdate,b.volume,b.turnover,e.ZJLXMainNetTur,"
        "ROW_NUMBER() OVER (PARTITION BY b.mktcode,b.tgtcode ORDER BY b.bizdate DESC) AS session_no "
        f"FROM `{database}`.`hsj_stock_hq_basic` AS b "
        f"LEFT JOIN `{database}`.`hsj_stock_hq_ext` AS e "
        "ON e.mktcode=b.mktcode AND e.tgtcode=b.tgtcode AND e.bizdate=b.bizdate) "
        "SELECT mktcode,tgtcode,bizdate,volume,turnover,ZJLXMainNetTur FROM ranked_source "
        "WHERE session_no<=10 ORDER BY mktcode,tgtcode,bizdate"
    )


def _bucket_oracle_source_sql(database: str, latest_date: str) -> str:
    return (
        "WITH sample_stocks AS ("
        "SELECT mktcode,tgtcode "
        f"FROM `{database}`.`hsj_stock_hq_basic` WHERE bizdate='{latest_date}' "
        "ORDER BY mktcode,tgtcode LIMIT 200) "
        "SELECT b.mktcode,b.tgtcode,b.bizdate,b.volume "
        f"FROM `{database}`.`hsj_stock_hq_basic` AS b "
        "INNER JOIN sample_stocks AS s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
        f"WHERE b.bizdate>=DATE_SUB('{latest_date}', INTERVAL 2 YEAR) "
        "AND b.bizdate<='" + latest_date + "' ORDER BY b.mktcode,b.tgtcode,b.bizdate"
    )


def _group_records(rows):
    grouped = defaultdict(list)
    for market, code, _date, volume, turnover, main_inflow in rows:
        grouped[(market, code)].append(
            {
                "volume": _numeric(volume),
                "turnover": _numeric(turnover),
                "main_inflow": _numeric(main_inflow),
            }
        )
    return grouped


def _numeric(value: str) -> float:
    if value in {"", "NULL", "\\N"}:
        return 0.0
    return float(value)


def _bucket_ordinal(raw_date: str, unit: str) -> int:
    current = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if unit == "年":
        return current.year
    if unit == "月":
        return current.year * 12 + current.month
    if unit == "季度":
        return current.year * 4 + (current.month - 1) // 3 + 1
    monday = current - timedelta(days=current.weekday())
    return (monday - date(1970, 1, 1)).days // 7


def _query_rows(args, sql: str):
    command = [
        str(args.client),
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
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [line.split("\t") for line in result.stdout.splitlines() if line.strip()]


def _row_hash(rows) -> str:
    payload = "\n".join("\t".join(map(str, row)) for row in sorted(rows))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
        "# Phase 9 交易序列时序语义真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- MySQL 协议兼容版本：`{report['mysql_protocol_version']}`",
        f"- 官方基础表行数：`{report['official_basic_rows']}`",
        f"- 独立 oracle 行数：`{report['oracle_rows']}`",
        f"- 日历桶 oracle：`{report['bucket_oracle_rows']}` 行 / `{report['bucket_oracle_stocks']}` 只固定样本股票",
        f"- 最新交易日股票数：`{report['latest_universe']}`",
        f"- 行集哈希一致：`{report['matched']}/{report['total']}`",
        "",
        "| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |",
        "|---|---:|---:|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['expected_count']} | {item['actual_count']} | "
            f"{'是' if item['matched'] else '否'} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> oracle 从 Doris 提取原始交易记录；日粒度覆盖全体最新股票，日历桶覆盖按稳定键排序的 200 只固定样本股票。时序与缺失桶判定由独立 Python 参考解释器完成，不复用生成 SQL 的窗口、桶或 CTE 逻辑。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
