from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.external.runtime import (
    default_benchmark_policy_catalog,
    default_external_index_quote_catalog,
    default_external_scope_catalog,
)
from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect independent Phase 47 benchmark-policy Doris evidence"
    )
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--performance-target-ms", type=float, default=10_000.0)
    parser.add_argument(
        "--json-output", default="reports/phase47_benchmark_policy_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase47_benchmark_policy_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    technical = f"`{args.database}`.`hsj_stock_hq_basic_technical`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    policy = default_benchmark_policy_catalog().resolve("大盘")
    quote = default_external_index_quote_catalog().resolve(policy.index_code)
    ai_scope = default_external_scope_catalog().resolve("ai").option
    benchmark_filter = (
        f"index_code='{policy.index_code}' AND snapshot_id='{quote.snapshot_id}'"
    )
    benchmark_rows_on_anchor = int(
        _query_rows(
            args,
            "SELECT COUNT(*) FROM `findsl_ext`.`index_quote` "
            f"WHERE {benchmark_filter} AND bizdate='{latest}'",
        )[0][0]
    )

    pct = "((q.lastPx-q.preClosePx)*100.0/NULLIF(q.preClosePx,0))"
    ai_membership = (
        "EXISTS (SELECT 1 FROM `findsl_ext`.`scope_membership` s "
        "WHERE s.mktcode=q.mktcode AND s.tgtcode=q.tgtcode "
        f"AND s.scope_code='{ai_scope.scope_code}' "
        f"AND s.snapshot_id='{ai_scope.snapshot_id}')"
    )
    benchmark_today = (
        "SELECT pct_change AS benchmark FROM `findsl_ext`.`index_quote` "
        f"WHERE {benchmark_filter} AND bizdate='{latest}'"
    )
    recent_lower = f"DATE_ADD(DATE_SUB('{latest}', INTERVAL '1' MONTH), INTERVAL '1' DAY)"
    cases = (
        {
            "name": "ai_top1_not_outperform_benchmark",
            "excel_row": 1870,
            "source": (
                "indicator('沪|深|京', 'ai', '涨跌幅', '今天', '', '', '') "
                "<= queryData('', '大盘', '涨跌幅', '今天', '') and "
                "rank('沪|深|京', 'ai', '涨幅', 'desc', '今天', '', '', '') = 1"
            ),
            "reference": (
                "WITH benchmark AS ("
                f"{benchmark_today}), ranked AS ("
                "SELECT q.mktcode,q.tgtcode,q.bizdate,"
                f"{pct} AS pct_change,ROW_NUMBER() OVER (ORDER BY {pct} DESC,"
                "q.mktcode ASC,q.tgtcode ASC) AS rn "
                f"FROM {basic} q WHERE q.bizdate='{latest}' "
                f"AND q.mktcode IN (0,1,103) AND {ai_membership}) "
                "SELECT r.mktcode,r.tgtcode,r.bizdate FROM ranked r "
                "CROSS JOIN benchmark b WHERE r.rn=1 AND r.pct_change<=b.benchmark"
            ),
            "required_fragments": (
                policy.index_code,
                quote.snapshot_id,
                ai_scope.snapshot_id,
                "hsj_stock_hq_basic` AS q_latest",
            ),
        },
        {
            "name": "today_gain_between_benchmark_and_one_percent",
            "excel_row": 4741,
            "source": (
                "indicator('', '', '涨幅', '今天', '', '', '') > "
                "queryData('', '大盘', '涨幅', '今天', '') and "
                "indicator('', '', '涨幅', '今天', '', '', '') < 1%"
            ),
            "reference": (
                f"WITH benchmark AS ({benchmark_today}) "
                "SELECT q.mktcode,q.tgtcode,q.bizdate "
                f"FROM {basic} q CROSS JOIN benchmark b WHERE q.bizdate='{latest}' "
                f"AND {pct}>b.benchmark AND {pct}<1"
            ),
            "required_fragments": (
                policy.index_code,
                quote.snapshot_id,
                "hsj_stock_hq_basic` AS q_latest",
            ),
        },
        {
            "name": "recent_month_benchmark_and_ma60",
            "excel_row": 5742,
            "source": (
                "indicator('', '', '涨跌幅', '近一月', '', '', '') > "
                "queryData('', '大盘', '涨跌幅', '近一月', '') and "
                "indicator('', '', '收盘价', '最新', '', '', '') > "
                "indicator('', '', '60日均线', '最新', '', '', '')"
            ),
            "reference": (
                "WITH benchmark AS (SELECT MAX_BY(pct_change,bizdate) AS value "
                "FROM `findsl_ext`.`index_quote` "
                f"WHERE {benchmark_filter} AND bizdate>={recent_lower} "
                f"AND bizdate<='{latest}'), stock_metric AS ("
                "SELECT q.mktcode,q.tgtcode,MAX_BY("
                f"{pct},q.bizdate) AS value FROM {basic} q "
                f"WHERE q.bizdate>={recent_lower} AND q.bizdate<='{latest}' "
                "GROUP BY q.mktcode,q.tgtcode) "
                "SELECT q.mktcode,q.tgtcode,q.bizdate "
                f"FROM {basic} q INNER JOIN {technical} t "
                "ON t.mktcode=q.mktcode AND t.tgtcode=q.tgtcode "
                "AND t.bizdate=q.bizdate INNER JOIN stock_metric s "
                "ON s.mktcode=q.mktcode AND s.tgtcode=q.tgtcode "
                f"CROSS JOIN benchmark b WHERE q.bizdate='{latest}' "
                "AND s.value>b.value AND q.closePx/10000.0>t.ma60"
            ),
            "required_fragments": (
                policy.index_code,
                quote.snapshot_id,
                "calendar_anchor",
                "official_technical",
            ),
        },
    )

    results = []
    for case in cases:
        generated_sql = compile_official(case["source"]).backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, case["reference"])}
        actual = set()
        timings = []
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {tuple(row[:3]) for row in _query_rows(args, generated_sql)}
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join(
            "\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated_sql}")
        )
        p95_ms = _nearest_rank(timings, 0.95)
        results.append(
            {
                "name": case["name"],
                "excel_row": case["excel_row"],
                "source": case["source"],
                "generated_sql": generated_sql,
                "reference_sql": case["reference"],
                "expected_count": len(expected),
                "actual_count": len(actual),
                "expected_sha256": _row_hash(expected),
                "actual_sha256": _row_hash(actual),
                "matched": expected == actual,
                "missing_sample": sorted(expected - actual)[:10],
                "extra_sample": sorted(actual - expected)[:10],
                "elapsed_ms": timings,
                "p95_ms": p95_ms,
                "under_performance_target": p95_ms < args.performance_target_ms,
                "structural_contract": all(
                    fragment in generated_sql
                    for fragment in case["required_fragments"]
                ),
                "explain_sha256": hashlib.sha256(
                    explain.encode("utf-8")
                ).hexdigest(),
                "explain_excerpt": "\n".join(explain.splitlines()[:80]),
            }
        )

    source_contract = benchmark_rows_on_anchor == 1
    passed = source_contract and all(
        item["matched"]
        and item["structural_contract"]
        and item["under_performance_target"]
        for item in results
    )
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "latest_data_date": latest,
        "repeats": args.repeats,
        "performance_target_ms": args.performance_target_ms,
        "benchmark_alias": policy.alias,
        "benchmark_index_code": policy.index_code,
        "benchmark_index_name": policy.index_name,
        "benchmark_policy_id": policy.policy_id,
        "benchmark_policy_source": policy.source,
        "benchmark_policy_effective_from": policy.effective_from,
        "benchmark_policy_rationale_url": policy.rationale_url,
        "quote_snapshot_id": quote.snapshot_id,
        "quote_source": quote.source,
        "benchmark_rows_on_anchor": benchmark_rows_on_anchor,
        "source_contract": source_contract,
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "structural_contracts": sum(item["structural_contract"] for item in results),
        "performance_passed": sum(
            item["under_performance_target"] for item in results
        ),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _query_rows(args, sql: str):
    command = [
        str(args.client),
        "--default-character-set=utf8mb4",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--user",
        args.user,
        "--skip-column-names",
        "--batch",
        "--raw",
        "--execute",
        sql,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
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
        "# Phase 47 大盘基准政策独立 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 官方行情锚点：`{report['latest_data_date']}`",
        f"- 基准政策：`{report['benchmark_policy_id']}`",
        f"- 大盘映射：`{report['benchmark_index_name']} ({report['benchmark_index_code']})`",
        f"- 指数行情快照：`{report['quote_snapshot_id']}`",
        f"- 锚点日指数记录：`{report['benchmark_rows_on_anchor']}`",
        f"- 独立参考 SQL 完整行集一致：`{report['matched']}/{report['total']}`",
        f"- 结构合同：`{report['structural_contracts']}/{report['total']}`",
        f"- 性能门禁：`{report['performance_passed']}/{report['total']}`",
        "",
        "| Excel 行 | 场景 | 参考行数 | 生成行数 | 哈希一致 | 结构合同 | P95/ms |",
        "|---:|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['excel_row']} | `{item['name']}` | {item['expected_count']} | "
            f"{item['actual_count']} | {'PASS' if item['matched'] else 'FAIL'} | "
            f"{'PASS' if item['structural_contract'] else 'FAIL'} | "
            f"{item['p95_ms']:.4f} |"
        )
    lines.extend(
        [
            "",
            "> 参考 SQL 独立写出沪深300基准值、AI 范围排名、近一月末值和 60 日均线条件；完整比较 `(mktcode,tgtcode,bizdate)` 行集，不以行数或抽样代替语义核验。",
            "",
            "> “大盘=沪深300”是版本化项目业务政策，不冒充赛题方唯一口径。赛题方若指定其他基准，只需替换政策目录和对应行情快照，无需修改 ANTLR、Typed AST、Logical IR、Physical IR 或 SQL 后端。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
