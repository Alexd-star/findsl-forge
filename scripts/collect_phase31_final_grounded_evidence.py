from __future__ import annotations

import argparse
import hashlib
import json
import time

from collect_phase30_grounded_event_evidence import (
    _git_head,
    _nearest_rank,
    _query_rows,
    _row_hash,
    _write_report,
)
from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Doris evidence for the final grounded migration gaps"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--json-output", default="reports/phase31_final_grounded_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase31_final_grounded_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    ext = f"`{args.database}`.`hsj_stock_hq_ext`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    fixed_start = "2025-10-09"

    fixed_since_reference = (
        "WITH bounded AS (SELECT b.mktcode,b.tgtcode,b.bizdate,b.lastPx,"
        "b.preClosePx,b.turnRatio,MAX(b.lastPx/10000.0) OVER(PARTITION BY "
        "b.mktcode,b.tgtcode ORDER BY b.bizdate ROWS BETWEEN UNBOUNDED PRECEDING "
        f"AND CURRENT ROW) AS period_high FROM {basic} b "
        f"WHERE b.bizdate>='{fixed_start}') "
        "SELECT mktcode,tgtcode,bizdate FROM bounded "
        f"WHERE bizdate='{latest}' AND lastPx/10000.0>=period_high "
        "AND ((lastPx-preClosePx)*100.0)/NULLIF(preClosePx,0)>6 "
        "AND turnRatio/10000.0>10"
    )
    stage_rank_reference = (
        "WITH positioned AS (SELECT b.mktcode,b.tgtcode,b.bizdate,b.lastPx,"
        "MIN(b.lastPx/10000.0) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY "
        "b.bizdate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS hist_low,"
        "MAX(b.lastPx/10000.0) OVER(PARTITION BY b.mktcode,b.tgtcode ORDER BY "
        f"b.bizdate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS hist_high FROM {basic} b),"
        " candidates AS (SELECT p.mktcode,p.tgtcode,p.bizdate,e.ZJLXMainNetTur AS metric "
        f"FROM positioned p JOIN {ext} e ON e.mktcode=p.mktcode AND e.tgtcode=p.tgtcode "
        "AND e.bizdate=p.bizdate WHERE p.mktcode=1 AND p.tgtcode BETWEEN '688000' AND '688999' "
        f"AND p.bizdate='{latest}' AND e.maAngle=45 AND CASE "
        "WHEN p.lastPx/10000.0 IS NULL OR p.hist_low IS NULL OR p.hist_high IS NULL THEN NULL "
        "WHEN p.lastPx/10000.0<=p.hist_low THEN '最低' "
        "WHEN p.lastPx/10000.0>=p.hist_high THEN '最高' "
        "WHEN (p.lastPx/10000.0-p.hist_low)/NULLIF(p.hist_high-p.hist_low,0)<=0.25 THEN '低' "
        "WHEN (p.lastPx/10000.0-p.hist_low)/NULLIF(p.hist_high-p.hist_low,0)>=0.75 THEN '高' "
        "ELSE '中' END='低'), ranked AS (SELECT mktcode,tgtcode,bizdate,"
        "ROW_NUMBER() OVER(ORDER BY CASE WHEN metric IS NULL THEN 1 ELSE 0 END,"
        "metric ASC,mktcode ASC,tgtcode ASC) AS rn FROM candidates) "
        "SELECT mktcode,tgtcode,bizdate FROM ranked WHERE rn<=5"
    )

    cases = (
        {
            "name": "fixed_since_record_high",
            "source": "record_high('', '', '', '2025年10月9日以来', '', '', '', '') = True and indicator('', '', '涨幅', '最新', '', '', '') > 6% and indicator('', '', '换手率', '最新', '', '', '') > 10%",
            "reference": fixed_since_reference,
            "required_sql": (
                "WHERE `q`.`bizdate` >= '2025-10-09'",
                "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
            ),
        },
        {
            "name": "event_candidate_then_rank",
            "source": "indicator('科创板', '', 'MA角度', '', '', '', '') = 45 and position('科创板', '', '', '历史', '目前', '', '', '') = '低' then rank('科创板', '', '主力净流入', 'asc', '', '', '', '') <= 5",
            "reference": stage_rank_reference,
            "required_sql": (
                "`stage_1_candidates_raw`",
                "ROW_NUMBER() OVER (ORDER BY",
                "`stage_1_ranked`.`stage_rank` <= 5",
            ),
        },
    )

    results = []
    for case in cases:
        compiled = compile_official(case["source"])
        generated = compiled.backend["sql"]
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
        structural = all(token in generated for token in case["required_sql"])
        results.append(
            {
                "name": case["name"],
                "source": case["source"],
                "selected_strategy": compiled.physical["selected_strategy"],
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
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "non_empty": sum(item["non_empty"] for item in results),
        "structural_contracts": sum(item["structural_contract"] for item in results),
        "under_performance_target": sum(item["p95_ms"] < 10_000 for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(
        report,
        args.json_output,
        args.report_output,
        title="Phase 31 最终有据迁移缺口 Doris 证据",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
