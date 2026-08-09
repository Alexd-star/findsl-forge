from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.physical.scopes import default_security_scope_catalog
from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Phase 19 security-name scope evidence on real Doris data"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase19_security_scope_doris.json")
    parser.add_argument("--report-output", default="reports/phase19_security_scope_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    security = f"`{args.database}`.`hsj_stock_code_info`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    recent_dates = [
        row[0]
        for row in _query_rows(
            args,
            f"SELECT bizdate FROM {basic} GROUP BY bizdate ORDER BY bizdate DESC LIMIT 5",
        )
    ]
    catalog = default_security_scope_catalog()
    live_security_rows = _query_rows(
        args,
        f"SELECT mktcode,tgtcode,name FROM {security} "
        "WHERE name IS NOT NULL AND name<>'' ORDER BY mktcode,tgtcode",
    )
    live_source_hash = hashlib.sha256(
        "\n".join("\t".join(row[:3]) for row in live_security_rows).encode("utf-8")
    ).hexdigest()
    source_hash_match = live_source_hash == catalog.source_sha256

    date_list = ",".join(f"'{value}'" for value in recent_dates)
    cases = (
        {
            "name": "exact_name_universe",
            "source": "indicator('', '华泰证券', '', '', '', '', '') = 'all'",
            "reference": (
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} AS b "
                f"INNER JOIN {security} AS s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name='华泰证券' AND b.bizdate='{latest}'"
            ),
        },
        {
            "name": "market_and_exact_name",
            "source": "indicator('创业板', '机器人', '', '', '', '', '') = 'all'",
            "reference": (
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} AS b "
                f"INNER JOIN {security} AS s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                "WHERE s.name='机器人' AND b.mktcode=0 "
                f"AND b.tgtcode>='300000' AND b.tgtcode<='301999' AND b.bizdate='{latest}'"
            ),
        },
        {
            "name": "explicit_name_and_code",
            "source": "indicator('', '珀莱雅(603605)', '', '', '', '', '') = 'all'",
            "reference": (
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} AS b "
                f"INNER JOIN {security} AS s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name='珀莱雅' AND s.mktcode=1 AND s.tgtcode='603605' "
                f"AND b.bizdate='{latest}'"
            ),
        },
        {
            "name": "direct_querydata_scalar",
            "source": (
                "indicator('沪', '', '成交量', '今日', '', '', '') > "
                "queryData('', '贵州茅台', '成交量', '今日', '')"
            ),
            "reference": (
                "WITH benchmark AS ("
                f"SELECT b.volume FROM {basic} AS b INNER JOIN {security} AS s "
                "ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name='贵州茅台' AND b.bizdate='{latest}') "
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} AS b "
                "CROSS JOIN benchmark AS q "
                f"WHERE b.mktcode=1 AND b.bizdate='{latest}' AND b.volume>q.volume"
            ),
        },
        {
            "name": "global_querydata_aggregate",
            "source": (
                "indicator('沪', '', '成交量', '近5日', '', 'AVG', '') > "
                "queryData('', '贵州茅台', '成交量', '近5日', 'AVG')"
            ),
            "reference": (
                "WITH candidate AS ("
                f"SELECT b.mktcode,b.tgtcode,AVG(b.volume) AS metric FROM {basic} AS b "
                f"WHERE b.mktcode=1 AND b.bizdate IN ({date_list}) GROUP BY b.mktcode,b.tgtcode), "
                "benchmark AS ("
                f"SELECT AVG(b.volume) AS metric FROM {basic} AS b INNER JOIN {security} AS s "
                "ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name='贵州茅台' AND b.bizdate IN ({date_list})) "
                f"SELECT a.mktcode,a.tgtcode,a.bizdate FROM {basic} AS a "
                "INNER JOIN candidate AS c ON c.mktcode=a.mktcode AND c.tgtcode=a.tgtcode "
                f"CROSS JOIN benchmark AS q WHERE a.bizdate='{latest}' AND c.metric>q.metric"
            ),
        },
        {
            "name": "rank_with_exact_name_scope",
            "source": "rank('沪', '华泰证券', '成交量', 'desc', '今日', '', '', '') <= 1",
            "reference": (
                "WITH ranked AS ("
                f"SELECT b.mktcode,b.tgtcode,b.bizdate,ROW_NUMBER() OVER (ORDER BY b.volume DESC,b.mktcode,b.tgtcode) AS rn "
                f"FROM {basic} AS b INNER JOIN {security} AS s "
                "ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name='华泰证券' AND b.mktcode=1 AND b.bizdate='{latest}') "
                "SELECT mktcode,tgtcode,bizdate FROM ranked WHERE rn<=1"
            ),
        },
        {
            "name": "exact_name_union",
            "source": "indicator('', '华泰证券|中科曙光', '', '', '', '', '') = 'all'",
            "reference": (
                f"SELECT b.mktcode,b.tgtcode,b.bizdate FROM {basic} AS b "
                f"INNER JOIN {security} AS s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
                f"WHERE s.name IN ('华泰证券','中科曙光') AND b.bizdate='{latest}'"
            ),
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
            actual = {tuple(row[:3]) for row in _query_rows(args, generated_sql)}
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        explain = "\n".join("\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated_sql}"))
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
                "p95_ms": _nearest_rank(timings, 0.95),
                "security_join": "hsj_stock_code_info" in generated_sql,
                "cross_join": "CROSS JOIN" in generated_sql,
                "explain_sha256": hashlib.sha256(explain.encode("utf-8")).hexdigest(),
                "explain_excerpt": "\n".join(explain.splitlines()[:80]),
            }
        )

    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    passed = source_hash_match and all(item["matched"] for item in results)
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "latest_data_date": latest,
        "security_catalog_rows": len(catalog.entries),
        "security_catalog_source_sha256": catalog.source_sha256,
        "live_security_source_sha256": live_source_hash,
        "security_catalog_source_match": source_hash_match,
        "repeats": args.repeats,
        "status": "PASS" if passed else "FAIL",
        "matched": sum(item["matched"] for item in results),
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
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 19 证券名称范围真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 最新数据日期：`{report['latest_data_date']}`",
        f"- 证券目录行数：`{report['security_catalog_rows']}`",
        f"- 目录与实时 Doris 源哈希一致：`{report['security_catalog_source_match']}`",
        f"- 完整行集哈希一致：`{report['matched']}/{report['total']}`",
        "",
        "| 场景 | 预期行数 | 实际行数 | 哈希一致 | Security Join | Cross Join | P95 ms |",
        "|---|---:|---:|---|---|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['expected_count']} | {item['actual_count']} | "
            f"{'是' if item['matched'] else '否'} | {item['security_join']} | "
            f"{item['cross_join']} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> 只有能在版本化官方证券主数据目录中精确解析的名称或“名称(六位代码)”才会进入 Physical IR。概念、行业、指数和自定义板块缺少成员关系时返回 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`，不会退化为全市场或空结果假成功。",
            "",
            "> `queryData` 的直接值和全局聚合值均以独立命名关系执行，再通过 Cross Join 进入候选证券谓词；它们不会把名称过滤错误施加到候选全集，也不会按候选证券键关联全局基准。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
