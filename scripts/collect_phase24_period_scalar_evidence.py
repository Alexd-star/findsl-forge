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
        description="Collect Phase 24 named period-scalar Doris evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--json-output", default="reports/phase24_period_scalar_doris.json")
    parser.add_argument("--report-output", default="reports/phase24_period_scalar_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    security = f"`{args.database}`.`hsj_stock_code_info`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    recent5 = f"SELECT bizdate FROM {basic} GROUP BY bizdate ORDER BY bizdate DESC LIMIT 5"
    week_start = (
        f"DATE_SUB(DATE_TRUNC((SELECT MAX(bizdate) FROM {basic}), 'WEEK'), INTERVAL '1' WEEK)"
    )
    week_end = (
        f"DATE_SUB(DATE_TRUNC((SELECT MAX(bizdate) FROM {basic}), 'WEEK'), INTERVAL '1' DAY)"
    )
    latest_rows = (
        f"SELECT mktcode,tgtcode,bizdate,volume,turnover FROM {basic} WHERE bizdate='{latest}'"
    )
    cases = (
        {
            "name": "period_scalar_vs_period_average",
            "source": (
                "indicator('', '', '成交量', '近5日', '', '', '') > "
                "indicator('', '', '成交量', '近5日', '', 'AVG', '')"
            ),
            "reference": (
                "WITH metrics AS (SELECT mktcode,tgtcode,MAX_BY(volume,bizdate) AS period_value,"
                f"AVG(volume) AS average_value FROM {basic} WHERE bizdate IN ({recent5}) "
                "GROUP BY mktcode,tgtcode) SELECT a.mktcode,a.tgtcode,a.bizdate FROM "
                f"({latest_rows}) a JOIN metrics m ON m.mktcode=a.mktcode AND m.tgtcode=a.tgtcode "
                "WHERE m.period_value>m.average_value"
            ),
        },
        {
            "name": "two_period_scalars_and_aggregate",
            "source": (
                "indicator('', '', '成交额', '近5日', '', '', '') > "
                "indicator('', '', '成交量', '近5日', '', '', '') and "
                "indicator('', '', '成交量', '近5日', '', 'AVG', '') > 0"
            ),
            "reference": (
                "WITH metrics AS (SELECT mktcode,tgtcode,MAX_BY(turnover,bizdate) AS turnover_value,"
                "MAX_BY(volume,bizdate) AS volume_value,AVG(volume) AS average_volume "
                f"FROM {basic} WHERE bizdate IN ({recent5}) GROUP BY mktcode,tgtcode) "
                f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM ({latest_rows}) a JOIN metrics m "
                "ON m.mktcode=a.mktcode AND m.tgtcode=a.tgtcode "
                "WHERE m.turnover_value>m.volume_value AND m.average_volume>0"
            ),
        },
        {
            "name": "period_querydata_cross_scalar",
            "source": (
                "indicator('', '', '成交量', '今日', '', '', '') < "
                "queryData('', '比亚迪', '成交量', '上周', '') and "
                "indicator('', '', '成交量', '近5日', '', 'AVG', '') > 0"
            ),
            "reference": (
                "WITH reference_value AS (SELECT MAX_BY(b.volume,b.bizdate) AS value "
                f"FROM {basic} b JOIN {security} s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name='比亚迪' AND b.bizdate>={week_start} AND b.bizdate<={week_end}), "
                "averages AS (SELECT mktcode,tgtcode,AVG(volume) AS value "
                f"FROM {basic} WHERE bizdate IN ({recent5}) GROUP BY mktcode,tgtcode) "
                f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM ({latest_rows}) a JOIN averages m "
                "ON m.mktcode=a.mktcode AND m.tgtcode=a.tgtcode CROSS JOIN reference_value r "
                "WHERE a.volume<r.value AND m.value>0"
            ),
        },
        {
            "name": "period_scalar_with_rank_arithmetic",
            "source": (
                "indicator('', '', '成交量', '上周', '', '', '') > 0 and "
                "rank('', '', '成交量', 'desc', '', '', '', '') / "
                "rank('', '', '成交额', 'desc', '', '', '', '') <= 1"
            ),
            "reference": (
                "WITH latest_rows AS ("
                f"{latest_rows}), period_value AS (SELECT mktcode,tgtcode,"
                f"MAX_BY(volume,bizdate) AS value FROM {basic} WHERE bizdate>={week_start} "
                f"AND bizdate<={week_end} GROUP BY mktcode,tgtcode), volume_rank AS ("
                "SELECT mktcode,tgtcode,ROW_NUMBER() OVER(ORDER BY volume DESC,mktcode,tgtcode) AS r0 "
                "FROM latest_rows), turnover_rank AS (SELECT mktcode,tgtcode,ROW_NUMBER() OVER("
                "ORDER BY turnover DESC,mktcode,tgtcode) AS r1 FROM latest_rows) "
                "SELECT a.mktcode,a.tgtcode,a.bizdate FROM latest_rows a JOIN period_value p "
                "ON p.mktcode=a.mktcode AND p.tgtcode=a.tgtcode JOIN volume_rank v "
                "ON v.mktcode=a.mktcode AND v.tgtcode=a.tgtcode JOIN turnover_rank t "
                "ON t.mktcode=a.mktcode AND t.tgtcode=a.tgtcode "
                "WHERE p.value>0 AND v.r0/NULLIF(t.r1,0)<=1"
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
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": compiled.physical.get("selected_strategy"),
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

    passed = all(item["matched"] and item["non_empty"] for item in results)
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
        "# Phase 24 命名周期标量真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 最新交易日：`{report['latest_data_date']}`",
        f"- 完整结果集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 非空结果：`{report['non_empty']}/{report['total']}`",
        "",
        "| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |",
        "|---|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['name']}` | `{item['selected_strategy']}` | "
            f"{item['expected_count']} | {item['actual_count']} | "
            f"{'PASS' if item['matched'] else 'FAIL'} | "
            f"{'yes' if item['non_empty'] else 'no'} | {item['p95_ms']:.4f} |"
        )
    lines.extend(
        [
            "",
            "每组均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本和 EXPLAIN 摘要。",
            "参考 SQL 独立计算周期末值、周期聚合、指定证券标量和横截面排名，不调用编译器 AST。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
