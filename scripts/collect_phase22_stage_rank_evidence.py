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
        description="Collect Phase 22 named-rank and candidate-stage evidence"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--json-output", default="reports/phase22_stage_rank_doris.json")
    parser.add_argument("--report-output", default="reports/phase22_stage_rank_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    latest_rows = f"SELECT mktcode,tgtcode,bizdate,volume,turnover FROM {basic} WHERE bizdate='{latest}'"
    recent30 = f"SELECT bizdate FROM {basic} GROUP BY bizdate ORDER BY bizdate DESC LIMIT 30"
    last_week_start = (
        f"DATE_SUB(DATE_TRUNC((SELECT MAX(bizdate) FROM {basic}), 'WEEK'), INTERVAL '1' WEEK)"
    )
    last_week_end = (
        f"DATE_SUB(DATE_TRUNC((SELECT MAX(bizdate) FROM {basic}), 'WEEK'), INTERVAL '1' DAY)"
    )
    cases = (
        {
            "name": "named_rank_arithmetic",
            "source": (
                "rank('', '', '成交量', 'desc', '', '', '', '') / "
                "rank('', '', '成交额', 'desc', '', '', '', '') <= 1"
            ),
            "reference": (
                f"WITH latest_rows AS ({latest_rows}), volume_rank AS ("
                "SELECT mktcode,tgtcode,ROW_NUMBER() OVER(ORDER BY volume DESC,mktcode,tgtcode) AS r0 "
                "FROM latest_rows), turnover_rank AS ("
                "SELECT mktcode,tgtcode,ROW_NUMBER() OVER(ORDER BY turnover DESC,mktcode,tgtcode) AS r1 "
                "FROM latest_rows) SELECT a.mktcode,a.tgtcode,a.bizdate FROM latest_rows a "
                "JOIN volume_rank v ON v.mktcode=a.mktcode AND v.tgtcode=a.tgtcode "
                "JOIN turnover_rank t ON t.mktcode=a.mktcode AND t.tgtcode=a.tgtcode "
                "WHERE v.r0/NULLIF(t.r1,0)<=1"
            ),
        },
        {
            "name": "named_rank_period_end_arithmetic",
            "source": (
                "rank('', '', '成交量', 'desc', '上周', '', '', '') / "
                "rank('', '', '成交额', 'desc', '上周', '', '', '') <= 1"
            ),
            "reference": (
                "WITH volume_metric AS (SELECT mktcode,tgtcode,MAX_BY(volume,bizdate) AS value "
                f"FROM {basic} WHERE bizdate>={last_week_start} AND bizdate<={last_week_end} "
                "GROUP BY mktcode,tgtcode), turnover_metric AS (SELECT mktcode,tgtcode,"
                f"MAX_BY(turnover,bizdate) AS value FROM {basic} WHERE bizdate>={last_week_start} "
                f"AND bizdate<={last_week_end} GROUP BY mktcode,tgtcode), volume_rank AS ("
                "SELECT mktcode,tgtcode,ROW_NUMBER() OVER(ORDER BY value DESC,mktcode,tgtcode) AS r0 "
                "FROM volume_metric), turnover_rank AS (SELECT mktcode,tgtcode,ROW_NUMBER() OVER("
                "ORDER BY value DESC,mktcode,tgtcode) AS r1 FROM turnover_metric) "
                f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM ({latest_rows}) a "
                "JOIN volume_rank v ON v.mktcode=a.mktcode AND v.tgtcode=a.tgtcode "
                "JOIN turnover_rank t ON t.mktcode=a.mktcode AND t.tgtcode=a.tgtcode "
                "WHERE v.r0/NULLIF(t.r1,0)<=1"
            ),
        },
        {
            "name": "chained_candidate_rank",
            "source": (
                "indicator('', '', '成交量', '', '', '', '') > 0 "
                "then rank('', '', '成交量', 'desc', '', '', '', '') <= 10 "
                "then rank('', '', '成交量', 'asc', '', '', '', '') <= 5"
            ),
            "reference": (
                "WITH initial_candidates AS (SELECT mktcode,tgtcode,MAX(bizdate) AS bizdate "
                f"FROM {basic} WHERE volume>0 GROUP BY mktcode,tgtcode), latest_metric AS ("
                f"{latest_rows}), first_rank AS (SELECT c.mktcode,c.tgtcode,c.bizdate,"
                "ROW_NUMBER() OVER(ORDER BY m.volume DESC,c.mktcode,c.tgtcode) AS rn "
                "FROM initial_candidates c JOIN latest_metric m ON m.mktcode=c.mktcode "
                "AND m.tgtcode=c.tgtcode), first_top AS (SELECT * FROM first_rank WHERE rn<=10), "
                "second_rank AS (SELECT f.mktcode,f.tgtcode,f.bizdate,ROW_NUMBER() OVER("
                "ORDER BY m.volume ASC,f.mktcode,f.tgtcode) AS rn FROM first_top f "
                "JOIN latest_metric m ON m.mktcode=f.mktcode AND m.tgtcode=f.tgtcode) "
                "SELECT mktcode,tgtcode,bizdate FROM second_rank WHERE rn<=5"
            ),
        },
        {
            "name": "aggregate_filter_then_rank",
            "source": (
                "indicator('', '', '成交量', '最近30日', '', 'SUM', '') "
                "between '[40,900000000000]' then "
                "rank('', '', '成交量', 'desc', '最近30日', '', 'MIN', '') <= 80"
            ),
            "reference": (
                "WITH aggregate_metric AS (SELECT mktcode,tgtcode,SUM(volume) AS total_volume,"
                f"MIN(volume) AS min_volume FROM {basic} WHERE bizdate IN ({recent30}) "
                "GROUP BY mktcode,tgtcode), candidates AS (SELECT a.mktcode,a.tgtcode,a.bizdate,"
                "m.min_volume FROM ("
                f"{latest_rows}) a JOIN aggregate_metric m ON m.mktcode=a.mktcode "
                "AND m.tgtcode=a.tgtcode WHERE m.total_volume BETWEEN 40 AND 900000000000), "
                "ranked AS (SELECT mktcode,tgtcode,bizdate,ROW_NUMBER() OVER("
                "ORDER BY min_volume DESC,mktcode,tgtcode) AS rn FROM candidates) "
                "SELECT mktcode,tgtcode,bizdate FROM ranked WHERE rn<=80"
            ),
        },
        {
            "name": "temporal_filter_then_period_rank",
            "source": (
                "indicator('', '', '成交量', '近三天', '', '', 'CONS=每天') > 0 "
                "then rank('', '', '成交额', 'asc', '上周', '', '', '') < 5%"
            ),
            "reference": (
                "WITH sequenced AS (SELECT mktcode,tgtcode,bizdate,volume,ROW_NUMBER() OVER("
                f"PARTITION BY mktcode,tgtcode ORDER BY bizdate DESC) AS seq FROM {basic}), "
                "candidates AS (SELECT mktcode,tgtcode FROM sequenced WHERE seq<=3 "
                "GROUP BY mktcode,tgtcode HAVING COUNT(*)>0 AND SUM(CASE WHEN volume>0 THEN 1 ELSE 0 END)=COUNT(*)), "
                "period_metric AS (SELECT mktcode,tgtcode,MAX_BY(turnover,bizdate) AS value "
                f"FROM {basic} WHERE bizdate>={last_week_start} AND bizdate<={last_week_end} "
                "GROUP BY mktcode,tgtcode), joined AS (SELECT c.mktcode,c.tgtcode,"
                f"'{latest}' AS bizdate,p.value FROM candidates c JOIN period_metric p "
                "ON p.mktcode=c.mktcode AND p.tgtcode=c.tgtcode), ranked AS ("
                "SELECT mktcode,tgtcode,bizdate,ROW_NUMBER() OVER(ORDER BY CASE WHEN value IS NULL THEN 1 ELSE 0 END,"
                "value ASC,mktcode,tgtcode) AS rn,COUNT(*) OVER() AS population FROM joined) "
                "SELECT mktcode,tgtcode,bizdate FROM ranked WHERE rn<CEIL(population*5/100.0)"
            ),
        },
        {
            "name": "parenthesized_stage_union",
            "source": (
                "(indicator('', '', '成交量', '', '', '', '') > 0 then "
                "rank('', '', '成交量', 'desc', '', '', '', '') = 1) or "
                "(indicator('', '', '成交量', '', '', '', '') < 0 then "
                "rank('', '', '成交量', 'asc', '', '', '', '') = 1)"
            ),
            "reference": (
                "WITH latest_metric AS ("
                f"{latest_rows}), positive_candidates AS (SELECT mktcode,tgtcode,MAX(bizdate) AS bizdate "
                f"FROM {basic} WHERE volume>0 GROUP BY mktcode,tgtcode), positive_rank AS ("
                "SELECT c.mktcode,c.tgtcode,c.bizdate,ROW_NUMBER() OVER(ORDER BY m.volume DESC,"
                "c.mktcode,c.tgtcode) AS rn FROM positive_candidates c JOIN latest_metric m "
                "ON m.mktcode=c.mktcode AND m.tgtcode=c.tgtcode), negative_candidates AS ("
                "SELECT mktcode,tgtcode,MAX(bizdate) AS bizdate "
                f"FROM {basic} WHERE volume<0 GROUP BY mktcode,tgtcode), negative_rank AS ("
                "SELECT c.mktcode,c.tgtcode,c.bizdate,ROW_NUMBER() OVER(ORDER BY m.volume ASC,"
                "c.mktcode,c.tgtcode) AS rn FROM negative_candidates c JOIN latest_metric m "
                "ON m.mktcode=c.mktcode AND m.tgtcode=c.tgtcode) "
                "SELECT mktcode,tgtcode,bizdate FROM positive_rank WHERE rn=1 UNION "
                "SELECT mktcode,tgtcode,bizdate FROM negative_rank WHERE rn=1"
            ),
        },
        {
            "name": "temporal_rank_percentage_range",
            "source": (
                "rank('', '', '成交量', 'desc', '近15天', '', '', 'CONS=3日') "
                "between '[5%,10%]'"
            ),
            "reference": (
                "WITH sequenced AS (SELECT mktcode,tgtcode,bizdate,volume,ROW_NUMBER() OVER("
                f"PARTITION BY mktcode,tgtcode ORDER BY bizdate DESC) AS seq FROM {basic}), "
                "daily AS (SELECT mktcode,tgtcode,bizdate,MAX(volume) AS value FROM sequenced "
                "WHERE seq<=15 GROUP BY mktcode,tgtcode,bizdate), ranked AS ("
                "SELECT mktcode,tgtcode,bizdate,ROW_NUMBER() OVER(PARTITION BY bizdate "
                "ORDER BY value DESC,mktcode,tgtcode) AS rn,COUNT(*) OVER(PARTITION BY bizdate) AS population "
                "FROM daily), marked AS (SELECT *,CASE WHEN rn>=CEIL(population*5/100.0) "
                "AND rn<=CEIL(population*10/100.0) THEN 1 ELSE 0 END AS matched FROM ranked), "
                "all_rows AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS all_seq "
                "FROM marked), hits AS (SELECT mktcode,tgtcode,bizdate,all_seq,ROW_NUMBER() OVER("
                "PARTITION BY mktcode,tgtcode ORDER BY bizdate) AS hit_seq FROM all_rows WHERE matched=1), "
                "runs AS (SELECT mktcode,tgtcode,all_seq-hit_seq AS grp,COUNT(*) AS run_length FROM hits "
                "GROUP BY mktcode,tgtcode,all_seq-hit_seq), qualified AS (SELECT mktcode,tgtcode "
                "FROM runs GROUP BY mktcode,tgtcode HAVING MAX(run_length)>=3) "
                f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM ({latest_rows}) a JOIN qualified q "
                "ON q.mktcode=a.mktcode AND q.tgtcode=a.tgtcode"
            ),
        },
    )

    results = []
    for case in cases:
        compiled = compile_official(case["source"])
        generated = compiled.backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, case["reference"])}
        elapsed = []
        actual = set()
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
        "# Phase 22 命名排名与候选集阶段真实 Doris 证据",
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
            "每个用例保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本与 EXPLAIN 摘要。",
            "参考 SQL 独立表达排名总体、候选集边界和时序连续性，不复用编译器生成 AST。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
