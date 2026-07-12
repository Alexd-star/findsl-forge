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
        description="Collect Phase 23 temporal composition and rank-range evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--json-output", default="reports/phase23_relational_doris.json")
    parser.add_argument("--report-output", default="reports/phase23_relational_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    latest_anchor = (
        f"SELECT mktcode,tgtcode,bizdate FROM {basic} WHERE bizdate='{latest}'"
    )
    cases = (
        {
            "name": "not_every_recent_five",
            "source": "indicator('', '', '成交量', '近5日', '', '', 'CONS!=每日') > 0",
            "reference": (
                "WITH source AS (SELECT mktcode,tgtcode,bizdate,volume,ROW_NUMBER() OVER("
                f"PARTITION BY mktcode,tgtcode ORDER BY bizdate DESC) AS seq FROM {basic}), "
                "metrics AS (SELECT mktcode,tgtcode,SUM(CASE WHEN volume>0 THEN 1 ELSE 0 END) AS hits,"
                "COUNT(*) AS total FROM source WHERE seq<=5 GROUP BY mktcode,tgtcode), qualified AS ("
                "SELECT mktcode,tgtcode FROM metrics WHERE total>0 AND hits<>total) "
                f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM ({latest_anchor}) a JOIN qualified q "
                "ON q.mktcode=a.mktcode AND q.tgtcode=a.tgtcode"
            ),
        },
        {
            "name": "aligned_temporal_arithmetic",
            "source": (
                "indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') / "
                "indicator('', '', '成交额', '最近10日', '', '', 'CONS=3日') > 0"
            ),
            "reference": _consecutive_reference(
                basic,
                latest_anchor,
                "volume/turnover>0",
                10,
                3,
            ),
        },
        {
            "name": "multi_resource_temporal_join",
            "source": (
                "indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') > "
                "indicator('', '', '5日均量线', '最近10日', '', '', 'CONS=3日')"
            ),
            "reference": _consecutive_reference(
                (
                    "(SELECT b.mktcode,b.tgtcode,b.bizdate,b.volume,t.volume_avg_5 "
                    f"FROM {basic} b JOIN {technical} t ON t.mktcode=b.mktcode "
                    "AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate)"
                ),
                latest_anchor,
                "volume>volume_avg_5",
                10,
                3,
            ),
        },
        {
            "name": "direct_rank_percentage_range",
            "source": (
                "rank('', '', '成交量', 'desc', '今日', '', '', '') "
                "between '[5%,10%]'"
            ),
            "reference": (
                "WITH ranked AS (SELECT mktcode,tgtcode,bizdate,ROW_NUMBER() OVER("
                "ORDER BY volume DESC,mktcode,tgtcode) AS rn,COUNT(*) OVER() AS population "
                f"FROM {basic} WHERE bizdate='{latest}') SELECT mktcode,tgtcode,bizdate FROM ranked "
                "WHERE rn>=CEIL(population*5/100.0) AND rn<=CEIL(population*10/100.0)"
            ),
        },
        {
            "name": "candidate_stage_rank_range",
            "source": (
                "indicator('', '', '成交量', '', '', '', '') > 0 then "
                "rank('', '', '成交额', 'desc', '', '', '', '') between '[5,10]'"
            ),
            "reference": (
                "WITH candidates AS (SELECT mktcode,tgtcode,MAX(bizdate) AS bizdate "
                f"FROM {basic} WHERE volume>0 GROUP BY mktcode,tgtcode), metric AS ("
                f"SELECT mktcode,tgtcode,turnover FROM {basic} WHERE bizdate='{latest}'), ranked AS ("
                "SELECT c.mktcode,c.tgtcode,c.bizdate,ROW_NUMBER() OVER(ORDER BY m.turnover DESC,"
                "c.mktcode,c.tgtcode) AS rn FROM candidates c JOIN metric m ON m.mktcode=c.mktcode "
                "AND m.tgtcode=c.tgtcode) SELECT mktcode,tgtcode,bizdate FROM ranked WHERE rn BETWEEN 5 AND 10"
            ),
        },
        {
            "name": "set_candidates_then_rank",
            "source": (
                "rank('', '', '成交量', 'desc', '', '', '', '') <= 20 and "
                "indicator('', '', '成交量', '', '', '', '') > 0 then "
                "rank('', '', '成交额', 'desc', '', '', '', '') <= 3"
            ),
            "reference": (
                "WITH latest_rows AS (SELECT mktcode,tgtcode,bizdate,volume,turnover "
                f"FROM {basic} WHERE bizdate='{latest}'), volume_rank AS (SELECT mktcode,tgtcode,bizdate,"
                "volume,turnover,ROW_NUMBER() OVER(ORDER BY volume DESC,mktcode,tgtcode) AS rn "
                "FROM latest_rows), candidates AS (SELECT * FROM volume_rank WHERE rn<=20 AND volume>0), "
                "turnover_rank AS (SELECT mktcode,tgtcode,bizdate,ROW_NUMBER() OVER(ORDER BY turnover DESC,"
                "mktcode,tgtcode) AS rn FROM candidates) SELECT mktcode,tgtcode,bizdate "
                "FROM turnover_rank WHERE rn<=3"
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


def _consecutive_reference(source, latest_anchor, predicate, lookback, threshold):
    return (
        "WITH source AS (SELECT base_rows.*,ROW_NUMBER() OVER("
        "PARTITION BY base_rows.mktcode,base_rows.tgtcode ORDER BY base_rows.bizdate DESC) AS seq "
        f"FROM {source} AS base_rows), eligible AS ("
        f"SELECT * FROM source WHERE seq<={lookback}), sequenced AS (SELECT *,ROW_NUMBER() OVER("
        "PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS all_seq FROM eligible), hits AS ("
        "SELECT mktcode,tgtcode,bizdate,all_seq,ROW_NUMBER() OVER(PARTITION BY mktcode,tgtcode "
        f"ORDER BY bizdate) AS hit_seq FROM sequenced WHERE {predicate}), runs AS (SELECT mktcode,tgtcode,"
        "all_seq-hit_seq AS grp,COUNT(*) AS n FROM hits GROUP BY mktcode,tgtcode,all_seq-hit_seq), "
        f"qualified AS (SELECT mktcode,tgtcode FROM runs GROUP BY mktcode,tgtcode HAVING MAX(n)>={threshold}) "
        f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM ({latest_anchor}) a JOIN qualified q "
        "ON q.mktcode=a.mktcode AND q.tgtcode=a.tgtcode"
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
        "# Phase 23 复合时序与排名区间真实 Doris 证据",
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
            "参考 SQL 独立重建时序连续段、跨表稳定键 Join、排名总体及候选阶段，不调用编译器 AST。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
