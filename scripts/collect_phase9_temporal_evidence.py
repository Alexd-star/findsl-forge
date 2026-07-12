from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from findsl.official.domain.temporal import evaluate_temporal_matches, parse_temporal_quantifier
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

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": protocol_version,
        "official_basic_rows": official_row_count,
        "latest_date": latest_date,
        "oracle_rows": len(rows),
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
            "> oracle 只从 Doris 提取最近 10 条原始交易记录，时序判定由独立 Python 参考解释器完成；它不复用生成 SQL 的窗口/CTE 逻辑。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
