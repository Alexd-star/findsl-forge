from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.external.runtime import (
    default_external_data_policy,
    default_external_scope_catalog,
)
from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect independent Phase 46 derived-scope Doris evidence"
    )
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--performance-target-ms", type=float, default=10_000.0)
    parser.add_argument(
        "--json-output", default="reports/phase46_derived_scope_doris.json"
    )
    parser.add_argument(
        "--report-output", default="reports/phase46_derived_scope_doris.md"
    )
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    scope_option = default_external_scope_catalog().resolve(
        "沪深300沪市指数"
    ).option
    policy = default_external_data_policy()
    industry = policy.industry
    instrument = policy.instrument_rule

    scope_count = int(
        _query_rows(
            args,
            "SELECT COUNT(*) FROM `findsl_ext`.`scope_membership` "
            f"WHERE scope_code='{scope_option.scope_code}' "
            f"AND snapshot_id='{scope_option.snapshot_id}'",
        )[0][0]
    )
    scope_markets = tuple(
        row[0]
        for row in _query_rows(
            args,
            "SELECT mktcode FROM `findsl_ext`.`scope_membership` "
            f"WHERE scope_code='{scope_option.scope_code}' "
            f"AND snapshot_id='{scope_option.snapshot_id}' GROUP BY mktcode "
            "ORDER BY mktcode",
        )
    )
    t0_member_count = int(
        _query_rows(
            args,
            "SELECT COUNT(*) FROM `findsl_ext`.`instrument_rule` "
            f"WHERE snapshot_id='{instrument.snapshot_id}' AND t0_eligible=TRUE",
        )[0][0]
    )

    main_board = (
        "((q.mktcode=1 AND (q.tgtcode BETWEEN '600000' AND '600999' "
        "OR q.tgtcode BETWEEN '601000' AND '601999' "
        "OR q.tgtcode BETWEEN '603000' AND '603999' "
        "OR q.tgtcode BETWEEN '605000' AND '605999')) "
        "OR (q.mktcode=0 AND (q.tgtcode BETWEEN '000000' AND '000999' "
        "OR q.tgtcode BETWEEN '001000' AND '001999' "
        "OR q.tgtcode BETWEEN '002000' AND '002999' "
        "OR q.tgtcode BETWEEN '003000' AND '003999')))"
    )
    star_board = "q.mktcode=1 AND q.tgtcode BETWEEN '688000' AND '688999'"
    index_scope = (
        "EXISTS (SELECT 1 FROM `findsl_ext`.`scope_membership` s "
        "WHERE s.mktcode=q.mktcode AND s.tgtcode=q.tgtcode "
        f"AND s.scope_code='{scope_option.scope_code}' "
        f"AND s.snapshot_id='{scope_option.snapshot_id}')"
    )

    cases = (
        {
            "name": "t0_instrument_rule",
            "source": "indicator('', '当天买当天卖', '是否T+0', '', '', '', '') = True",
            "reference": (
                f"SELECT q.mktcode,q.tgtcode,q.bizdate FROM {basic} q "
                f"WHERE q.bizdate='{latest}' AND EXISTS (SELECT 1 "
                "FROM `findsl_ext`.`instrument_rule` r "
                "WHERE r.mktcode=q.mktcode AND r.tgtcode=q.tgtcode "
                f"AND r.snapshot_id='{instrument.snapshot_id}' "
                "AND r.t0_eligible=TRUE)"
            ),
            "required_fragments": ("instrument_rule", "t0_eligible"),
        },
        {
            "name": "csi300_sse_main_board_industry_avg",
            "source": (
                "indicator('', '沪深300沪市指数&沪深主板注册制', '总市值', '', '', '', '') "
                "> belong_industry('', '沪深300沪市指数&沪深主板注册制', "
                "'总市值', '', 'AVG')"
            ),
            "reference": _industry_reference(
                basic,
                latest,
                f"{index_scope} AND {main_board}",
                "AVG",
                industry,
            ),
            "required_fragments": (
                scope_option.snapshot_id,
                "600000",
                "605999",
                "000000",
                "003999",
            ),
        },
        {
            "name": "star_registration_industry_min",
            "source": (
                "indicator('', '科创板注册制', '总市值', '', '', '', '') "
                "> belong_industry('', '科创板注册制', '总市值', '', 'MIN')"
            ),
            "reference": _industry_reference(
                basic,
                latest,
                star_board,
                "MIN",
                industry,
            ),
            "required_fragments": ("688000", "688999"),
        },
    )

    results = []
    for case in cases:
        generated_sql = compile_official(case["source"]).backend["sql"]
        expected = {tuple(row[:3]) for row in _query_rows(args, case["reference"])}
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {
                tuple(row[:3]) for row in _query_rows(args, generated_sql)
            }
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join(
            "\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated_sql}")
        )
        p95_ms = _nearest_rank(timings, 0.95)
        structural_contract = all(
            fragment in generated_sql for fragment in case["required_fragments"]
        )
        results.append(
            {
                "name": case["name"],
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
                "structural_contract": structural_contract,
                "explain_sha256": hashlib.sha256(explain.encode("utf-8")).hexdigest(),
                "explain_excerpt": "\n".join(explain.splitlines()[:80]),
            }
        )

    source_contract = (
        scope_option.source == "csindex"
        and scope_count == 189
        and scope_markets == ("1",)
    )
    passed = source_contract and all(
        item["matched"]
        and item["structural_contract"]
        and item["under_performance_target"]
        for item in results
    )
    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "latest_data_date": latest,
        "repeats": args.repeats,
        "performance_target_ms": args.performance_target_ms,
        "scope_source": scope_option.source,
        "scope_code": scope_option.scope_code,
        "scope_snapshot_id": scope_option.snapshot_id,
        "scope_member_count": scope_count,
        "scope_market_codes": scope_markets,
        "scope_source_contract": source_contract,
        "t0_eligible_member_count": t0_member_count,
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "structural_contracts": sum(
            item["structural_contract"] for item in results
        ),
        "performance_passed": sum(
            item["under_performance_target"] for item in results
        ),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _industry_reference(basic, latest, scope_predicate, function, policy):
    return (
        "WITH scoped AS ("
        "SELECT q.mktcode,q.tgtcode,q.bizdate,"
        "(q.lastPx/10000.0)*q.totalShare AS metric "
        f"FROM {basic} q WHERE q.bizdate='{latest}' AND ({scope_predicate})), "
        "industry_stat AS ("
        f"SELECT i.industry_code,{function}(s.metric) AS baseline "
        "FROM scoped s INNER JOIN `findsl_ext`.`industry_membership` i "
        "ON i.mktcode=s.mktcode AND i.tgtcode=s.tgtcode "
        f"WHERE i.snapshot_id='{policy.snapshot_id}' "
        f"AND i.classification_system='{policy.classification_system}' "
        f"AND i.industry_level='{policy.industry_level}' GROUP BY i.industry_code) "
        "SELECT s.mktcode,s.tgtcode,s.bizdate FROM scoped s "
        "INNER JOIN `findsl_ext`.`industry_membership` i "
        "ON i.mktcode=s.mktcode AND i.tgtcode=s.tgtcode "
        "INNER JOIN industry_stat a ON a.industry_code=i.industry_code "
        f"WHERE i.snapshot_id='{policy.snapshot_id}' "
        f"AND i.classification_system='{policy.classification_system}' "
        f"AND i.industry_level='{policy.industry_level}' AND s.metric>a.baseline"
    )


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
        "# Phase 46 派生范围独立 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 最新行情日期：`{report['latest_data_date']}`",
        f"- 中证 000972 官方快照：`{report['scope_snapshot_id']}`",
        f"- 中证 000972 成员数：`{report['scope_member_count']}`",
        f"- 独立参考 SQL 完整行集一致：`{report['matched']}/{report['total']}`",
        f"- 结构合同：`{report['structural_contracts']}/{report['total']}`",
        f"- 性能门禁：`{report['performance_passed']}/{report['total']}`",
        "",
        "| 场景 | 参考行数 | 生成行数 | 哈希一致 | 结构合同 | P95/ms |",
        "|---|---:|---:|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['name']}` | {item['expected_count']} | "
            f"{item['actual_count']} | {'PASS' if item['matched'] else 'FAIL'} | "
            f"{'PASS' if item['structural_contract'] else 'FAIL'} | "
            f"{item['p95_ms']:.4f} |"
        )
    lines.extend(
        [
            "",
            "> 参考 SQL 独立写出交易规则存在性、交易所代码范围和行业分组聚合，未复用编译器生成 SQL。完整三列结果集按稳定证券键比较，不以抽样或仅比较行数代替语义核验。",
            "",
            f"> 当前 instrument_rule 中 T+0 合资格 A 股为 {report['t0_eligible_member_count']} 只，因此 T+0 用例空结果是版本化交易规则数据的真实结论，不是固定空查询。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
