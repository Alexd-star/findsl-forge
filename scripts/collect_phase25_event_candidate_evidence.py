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
        description="Collect Phase 25 keyed event-candidate Doris evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--json-output", default="reports/phase25_event_candidate_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase25_event_candidate_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    security = f"`{args.database}`.`hsj_stock_code_info`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    recent3 = _recent_sessions(basic, 3)
    recent5 = _recent_sessions(basic, 5)
    cases = (
        {
            "name": "period_record_high_and_grouped_average",
            "source": (
                "record_high('', '', '成交量', '20日', '近5日', '', '', '') = True "
                "and indicator('', '', '成交量', '近5日', '', 'AVG', '') > 0"
            ),
            "reference": (
                "WITH event_rows AS (SELECT mktcode,tgtcode,bizdate,volume,"
                "MAX(volume) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                "ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS window_max "
                f"FROM {basic}), event_keys AS (SELECT DISTINCT mktcode,tgtcode "
                f"FROM event_rows WHERE bizdate IN ({recent5}) AND volume>=window_max), "
                "metric_keys AS (SELECT mktcode,tgtcode FROM "
                f"{basic} WHERE bizdate IN ({recent5}) GROUP BY mktcode,tgtcode "
                "HAVING AVG(volume)>0) SELECT a.mktcode,a.tgtcode,a.bizdate "
                f"FROM {basic} a JOIN event_keys e ON e.mktcode=a.mktcode "
                "AND e.tgtcode=a.tgtcode JOIN metric_keys m ON m.mktcode=a.mktcode "
                f"AND m.tgtcode=a.tgtcode WHERE a.bizdate='{latest}'"
            ),
        },
        {
            "name": "period_event_absence_uses_decidable_universe",
            "source": (
                "cross_down('', '', '最新价', '10日均线', '近三天', '', '') = False "
                "and indicator('', '', '成交量', '今日', '', '', '') > 0"
            ),
            "reference": (
                "WITH joined AS (SELECT b.mktcode,b.tgtcode,b.bizdate,b.volume,"
                "b.lastPx/10000.0 AS px,t.ma10 FROM "
                f"{basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate), event_rows AS ("
                "SELECT mktcode,tgtcode,bizdate,volume,px<ma10 AND "
                "LAG(px) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate)>=LAG(ma10) "
                "OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS occurred "
                "FROM joined), eligible AS (SELECT DISTINCT mktcode,tgtcode FROM event_rows "
                f"WHERE bizdate IN ({recent3}) AND occurred IS NOT NULL), occurred AS ("
                "SELECT DISTINCT mktcode,tgtcode FROM event_rows "
                f"WHERE bizdate IN ({recent3}) AND occurred=TRUE), absent AS ("
                "SELECT e.mktcode,e.tgtcode FROM eligible e LEFT ANTI JOIN occurred o "
                "ON o.mktcode=e.mktcode AND o.tgtcode=e.tgtcode) "
                "SELECT b.mktcode,b.tgtcode,b.bizdate FROM "
                f"{basic} b JOIN absent a ON a.mktcode=b.mktcode AND a.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}' AND b.volume>0"
            ),
        },
        {
            "name": "latest_position_and_exact_security_scalar",
            "source": (
                "position('', '', '量比', '60日', '今日', '', '', '') = '高' and "
                "indicator('', '', '最新价', '今日', '', '', '') < "
                "queryData('', '比亚迪', '最新价', '今日', '')"
            ),
            "reference": (
                "WITH positioned AS (SELECT mktcode,tgtcode,bizdate,lastPx,"
                "quantRatio/10000.0 AS value,MIN(quantRatio/10000.0) OVER("
                "PARTITION BY mktcode,tgtcode ORDER BY bizdate ROWS BETWEEN 59 PRECEDING "
                "AND CURRENT ROW) AS minimum,MAX(quantRatio/10000.0) OVER("
                "PARTITION BY mktcode,tgtcode ORDER BY bizdate ROWS BETWEEN 59 PRECEDING "
                f"AND CURRENT ROW) AS maximum FROM {basic}), reference_value AS ("
                "SELECT b.lastPx/10000.0 AS value FROM "
                f"{basic} b JOIN {security} s ON s.mktcode=b.mktcode AND "
                f"s.tgtcode=b.tgtcode WHERE s.name='比亚迪' AND b.bizdate='{latest}') "
                "SELECT p.mktcode,p.tgtcode,p.bizdate FROM positioned p CROSS JOIN "
                f"reference_value r WHERE p.bizdate='{latest}' AND p.value>p.minimum "
                "AND p.value<p.maximum AND (p.value-p.minimum)/NULLIF(p.maximum-p.minimum,0)>=0.75 "
                "AND p.lastPx/10000.0<r.value"
            ),
        },
        {
            "name": "event_union_and_multi_growth_relation",
            "source": (
                "(cross_above('', '', '20日均线', '60日均线', '近五天', '', '') = True "
                "or cross_down('', '', '20日均线', '60日均线', '近五天', '', '') = True) "
                "and indicator('', '', '20日均线', '近五天', '', 'GROWTH_RISE', '') > -1000 "
                "and indicator('', '', '60日均线', '近五天', '', 'GROWTH_RISE', '') > -1000"
            ),
            "reference": (
                "WITH joined AS (SELECT b.mktcode,b.tgtcode,b.bizdate,t.ma20,t.ma60 "
                f"FROM {basic} b LEFT JOIN {technical} t ON t.mktcode=b.mktcode "
                "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate), event_rows AS ("
                "SELECT mktcode,tgtcode,bizdate,(ma20>ma60 AND LAG(ma20) OVER("
                "PARTITION BY mktcode,tgtcode ORDER BY bizdate)<=LAG(ma60) OVER("
                "PARTITION BY mktcode,tgtcode ORDER BY bizdate)) OR (ma20<ma60 AND "
                "LAG(ma20) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate)>=LAG(ma60) "
                "OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate)) AS occurred "
                "FROM joined), event_keys AS (SELECT DISTINCT mktcode,tgtcode FROM event_rows "
                f"WHERE bizdate IN ({recent5}) AND occurred=TRUE), metrics AS ("
                "SELECT mktcode,tgtcode,(MAX_BY(ma20,bizdate)-MIN_BY(ma20,bizdate))*100/"
                "NULLIF(ABS(MIN_BY(ma20,bizdate)),0) AS growth20,(MAX_BY(ma60,bizdate)-"
                "MIN_BY(ma60,bizdate))*100/NULLIF(ABS(MIN_BY(ma60,bizdate)),0) AS growth60 "
                f"FROM joined WHERE bizdate IN ({recent5}) GROUP BY mktcode,tgtcode) "
                "SELECT b.mktcode,b.tgtcode,b.bizdate FROM "
                f"{basic} b JOIN event_keys e ON e.mktcode=b.mktcode AND e.tgtcode=b.tgtcode "
                "JOIN metrics m ON m.mktcode=b.mktcode AND m.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}' AND m.growth20>-1000 AND m.growth60>-1000"
            ),
        },
        {
            "name": "different_event_and_indicator_date_scopes",
            "source": (
                "record_high('', '', '成交量', '20日', '今日', '', '', '') = True "
                "and indicator('', '', '成交量', '近三天', '', '', '') > 0"
            ),
            "reference": (
                "WITH event_rows AS (SELECT mktcode,tgtcode,bizdate,volume,"
                "MAX(volume) OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate "
                "ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS window_max "
                f"FROM {basic}), event_keys AS (SELECT DISTINCT mktcode,tgtcode "
                f"FROM event_rows WHERE bizdate='{latest}' AND volume>=window_max), "
                "indicator_keys AS (SELECT DISTINCT mktcode,tgtcode FROM "
                f"{basic} WHERE bizdate IN ({recent3}) AND volume>0) "
                "SELECT b.mktcode,b.tgtcode,b.bizdate FROM "
                f"{basic} b JOIN event_keys e ON e.mktcode=b.mktcode AND e.tgtcode=b.tgtcode "
                "JOIN indicator_keys i ON i.mktcode=b.mktcode AND i.tgtcode=b.tgtcode "
                f"WHERE b.bizdate='{latest}'"
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


def _recent_sessions(table: str, amount: int) -> str:
    return (
        f"SELECT bizdate FROM {table} GROUP BY bizdate "
        f"ORDER BY bizdate DESC LIMIT {amount}"
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
        "# Phase 25 证券键事件候选关系真实 Doris 证据",
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
            "参考 SQL 独立实现证券键集合交并差、事件窗口、三值可判定全集、最新快照回连和聚合关系，不调用编译器 AST。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
