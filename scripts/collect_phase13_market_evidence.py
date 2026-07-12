from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.pipeline import compile_official


CASES = (
    (
        "star_market",
        "科创板",
        "b.mktcode=1 AND b.tgtcode>='688000' AND b.tgtcode<='688999'",
    ),
    (
        "chinext_market",
        "创业板",
        "b.mktcode=0 AND ((b.tgtcode>='300000' AND b.tgtcode<='300999') "
        "OR (b.tgtcode>='301000' AND b.tgtcode<='301999'))",
    ),
    (
        "main_board_union",
        "沪主板|深主板",
        "((b.mktcode=1 AND ((b.tgtcode>='600000' AND b.tgtcode<='600999') "
        "OR (b.tgtcode>='601000' AND b.tgtcode<='601999') "
        "OR (b.tgtcode>='603000' AND b.tgtcode<='603999') "
        "OR (b.tgtcode>='605000' AND b.tgtcode<='605999'))) "
        "OR (b.mktcode=0 AND ((b.tgtcode>='000000' AND b.tgtcode<='000999') "
        "OR (b.tgtcode>='001000' AND b.tgtcode<='001999') "
        "OR (b.tgtcode>='002000' AND b.tgtcode<='002999') "
        "OR (b.tgtcode>='003000' AND b.tgtcode<='003999'))))",
    ),
    (
        "precedence_union_intersection_not",
        "沪|深&^创业板",
        "(b.mktcode=1 OR (b.mktcode=0 AND NOT (b.mktcode=0 AND "
        "((b.tgtcode>='300000' AND b.tgtcode<='300999') OR "
        "(b.tgtcode>='301000' AND b.tgtcode<='301999')))))",
    ),
    (
        "double_exclusion_beijing",
        "^沪&^深",
        "b.mktcode<>1 AND b.mktcode<>0",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect typed market-set evidence on a real Doris snapshot"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase13_market_doris.json")
    parser.add_argument("--report-output", default="reports/phase13_market_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    latest_date = _query_rows(
        args,
        f"SELECT MAX(bizdate) FROM `{args.database}`.`hsj_stock_hq_basic`",
    )[0][0]
    quality_row = _query_rows(
        args,
        "SELECT COUNT(*),SUM(kcbFlag),SUM(gemFlag),SUM(bShareFlag) "
        f"FROM `{args.database}`.`hsj_stock_code_info`",
    )[0]
    flag_audit = {
        "row_count": int(quality_row[0]),
        "kcb_flag_true": int(quality_row[1]),
        "gem_flag_true": int(quality_row[2]),
        "b_share_flag_true": int(quality_row[3]),
    }
    inferred_profile = {
        "star_688": _count_codes(args, "mktcode=1 AND tgtcode>='688000' AND tgtcode<='688999'"),
        "chinext_300_301": _count_codes(
            args,
            "mktcode=0 AND ((tgtcode>='300000' AND tgtcode<='300999') "
            "OR (tgtcode>='301000' AND tgtcode<='301999'))",
        ),
        "sh_main_600_601_603_605": _count_codes(
            args,
            "mktcode=1 AND (LEFT(tgtcode,3) IN ('600','601','603','605'))",
        ),
        "sz_main_000_001_002_003": _count_codes(
            args,
            "mktcode=0 AND (LEFT(tgtcode,3) IN ('000','001','002','003'))",
        ),
        "beijing_920": _count_codes(
            args,
            "mktcode=103 AND tgtcode>='920000' AND tgtcode<='920999'",
        ),
    }

    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    if not doris_versions:
        raise RuntimeError("SHOW FRONTENDS did not expose a Doris build version")

    results = []
    for name, market, reference_predicate in CASES:
        source = (
            f"indicator('{market}', '', '成交量', '今日', '', '', '') > 100"
        )
        reference_sql = (
            "SELECT b.mktcode,b.tgtcode,b.bizdate "
            f"FROM `{args.database}`.`hsj_stock_hq_basic` AS b "
            f"WHERE b.bizdate='{latest_date}' AND b.volume>100 AND {reference_predicate}"
        )
        expected = {tuple(row[:3]) for row in _query_rows(args, reference_sql)}
        generated_sql = compile_official(source).backend["sql"]
        timings = []
        actual = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual = {
                tuple(row[:3]) for row in _query_rows(args, generated_sql)
            }
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        results.append(
            {
                "name": name,
                "source": source,
                "generated_sql": generated_sql,
                "reference_sql": reference_sql,
                "expected_count": len(expected),
                "actual_count": len(actual),
                "expected_sha256": _row_hash(expected),
                "actual_sha256": _row_hash(actual),
                "matched": expected == actual,
                "missing_sample": sorted(expected - actual)[:10],
                "extra_sample": sorted(actual - expected)[:10],
                "elapsed_ms": timings,
                "p95_ms": _nearest_rank(timings, 0.95),
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": _query_rows(args, "SELECT VERSION()")[0][0],
        "latest_date": latest_date,
        "operator_precedence": ["^", "&", "|"],
        "flag_audit": flag_audit,
        "inferred_code_profile": inferred_profile,
        "repeats": args.repeats,
        "status": "PASS" if all(item["matched"] for item in results) else "FAIL",
        "matched": sum(item["matched"] for item in results),
        "total": len(results),
        "cases": results,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _count_codes(args, predicate: str) -> int:
    return int(
        _query_rows(
            args,
            f"SELECT COUNT(*) FROM `{args.database}`.`hsj_stock_code_info` WHERE {predicate}",
        )[0][0]
    )


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
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit = report["flag_audit"]
    lines = [
        "# Phase 13 Typed Market Set IR 真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- 运算优先级：`{' > '.join(report['operator_precedence'])}`",
        f"- 行集哈希一致：`{report['matched']}/{report['total']}`",
        f"- 代码表：`{audit['row_count']}` 行；kcb/gem/B-share flag 真值："
        f"`{audit['kcb_flag_true']}/{audit['gem_flag_true']}/{audit['b_share_flag_true']}`",
        "",
        "## 代码区间画像",
        "",
        "| 受控集合 | 代码表数量 |",
        "|---|---:|",
    ]
    for key, value in report["inferred_code_profile"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## 行集等价",
            "",
            "| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |",
            "|---|---:|---:|---|---:|",
        ]
    )
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {item['expected_count']} | {item['actual_count']} | "
            f"{'是' if item['matched'] else '否'} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> 官方 schema 将板块标识注明为需要通过代码表计算，但原始数据中的三个相关 flag 全为 false。本阶段不改写官方原始文件，而是以 mktcode 与六位 tgtcode 的受控区间生成集合谓词；reference SQL 独立书写相同集合定义并比较完整结果行集。境外市场和缺失市场仍返回 DATA_UNAVAILABLE，不生成空结果占位 SQL。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
