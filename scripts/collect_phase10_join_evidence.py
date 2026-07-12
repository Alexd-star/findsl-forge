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
    {
        "name": "basic_ext_latest",
        "source": (
            "indicator('', '', '成交量', '今日', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '今日', '', '', '') > 0"
        ),
        "joins": ("official_basic", "official_ext"),
        "where": "b.volume > 100 AND e.ZJLXMainNetTur > 0",
    },
    {
        "name": "basic_security_latest",
        "source": (
            "indicator('', '', '成交量', '今日', '', '', '') > 100 and "
            "indicator('', '', 'ST股票标识', '今日', '', '', '') = False"
        ),
        "joins": ("official_basic", "official_security"),
        "where": "b.volume > 100 AND s.stFlag = FALSE",
    },
    {
        "name": "ext_security_latest",
        "source": (
            "indicator('', '', '主力净流入', '今日', '', '', '') > 0 and "
            "indicator('', '', 'ST股票标识', '今日', '', '', '') = False"
        ),
        "joins": ("official_basic", "official_ext", "official_security"),
        "where": "e.ZJLXMainNetTur > 0 AND s.stFlag = FALSE",
    },
    {
        "name": "basic_ext_security_latest",
        "source": (
            "indicator('', '', '成交量', '今日', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '今日', '', '', '') > 0 and "
            "indicator('', '', 'ST股票标识', '今日', '', '', '') = False"
        ),
        "joins": ("official_basic", "official_ext", "official_security"),
        "where": "b.volume > 100 AND e.ZJLXMainNetTur > 0 AND s.stFlag = FALSE",
    },
    {
        "name": "basic_technical_latest",
        "source": (
            "indicator('', '', '成交量', '今日', '', '', '') > 100 and "
            "indicator('', '', '5日均线', '今日', '', '', '') > 0"
        ),
        "joins": ("official_basic", "official_technical"),
        "where": "b.volume > 100 AND t.ma5 > 0",
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect independent Phase 10 stable-key join evidence on Doris"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output", default="reports/phase10_join_doris.json")
    parser.add_argument("--report-output", default="reports/phase10_join_doris.md")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    protocol_version = _query_rows(args, "SELECT VERSION()")[0][0]
    frontend_rows = _query_rows(args, "SHOW FRONTENDS")
    doris_versions = sorted(
        value
        for value in {item for row in frontend_rows for item in row}
        if value.lower().startswith("doris-")
    )
    if not doris_versions:
        raise RuntimeError("SHOW FRONTENDS did not expose a Doris build version")
    latest_date = _query_rows(
        args,
        f"SELECT MAX(bizdate) FROM `{args.database}`.`hsj_stock_hq_basic`",
    )[0][0]
    row_counts = {
        table: int(
            _query_rows(
                args,
                f"SELECT COUNT(*) FROM `{args.database}`.`{table}`",
            )[0][0]
        )
        for table in (
            "hsj_stock_hq_basic",
            "hsj_stock_hq_ext",
            "hsj_stock_code_info",
            "hsj_stock_hq_basic_technical",
        )
    }

    cases = []
    for case in CASES:
        expected_sql = _reference_sql(args.database, latest_date, case["joins"], case["where"])
        expected_rows = {tuple(row[:3]) for row in _query_rows(args, expected_sql)}
        compiled = compile_official(case["source"])
        generated_sql = compiled.backend["sql"]
        timings = []
        actual_rows = set()
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual_rows = {
                tuple(row[:3]) for row in _query_rows(args, generated_sql)
            }
            timings.append(round((time.perf_counter_ns() - started) / 1_000_000, 4))
        cases.append(
            {
                "name": case["name"],
                "source": case["source"],
                "resources": list(case["joins"]),
                "generated_sql": generated_sql,
                "reference_sql": expected_sql,
                "expected_count": len(expected_rows),
                "actual_count": len(actual_rows),
                "expected_sha256": _row_hash(expected_rows),
                "actual_sha256": _row_hash(actual_rows),
                "matched": expected_rows == actual_rows,
                "missing_sample": sorted(expected_rows - actual_rows)[:10],
                "extra_sample": sorted(actual_rows - expected_rows)[:10],
                "elapsed_ms": timings,
                "p95_ms": _nearest_rank(timings, 0.95),
            }
        )

    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "doris_versions": doris_versions,
        "mysql_protocol_version": protocol_version,
        "latest_date": latest_date,
        "row_counts": row_counts,
        "repeats": args.repeats,
        "status": "PASS" if all(item["matched"] for item in cases) else "FAIL",
        "matched": sum(item["matched"] for item in cases),
        "total": len(cases),
        "cases": cases,
    }
    _write_report(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _reference_sql(database: str, latest_date: str, resources, where: str) -> str:
    sql = (
        "SELECT b.mktcode,b.tgtcode,b.bizdate "
        f"FROM `{database}`.`hsj_stock_hq_basic` AS b "
    )
    if "official_ext" in resources:
        sql += (
            f"INNER JOIN `{database}`.`hsj_stock_hq_ext` AS e "
            "ON e.mktcode=b.mktcode AND e.tgtcode=b.tgtcode AND e.bizdate=b.bizdate "
        )
    if "official_security" in resources:
        sql += (
            f"INNER JOIN `{database}`.`hsj_stock_code_info` AS s "
            "ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode "
        )
    if "official_technical" in resources:
        sql += (
            f"INNER JOIN `{database}`.`hsj_stock_hq_basic_technical` AS t "
            "ON t.mktcode=b.mktcode AND t.tgtcode=b.tgtcode AND t.bizdate=b.bizdate "
        )
    return f"{sql}WHERE b.bizdate='{latest_date}' AND {where}"


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
    lines = [
        "# Phase 10 多资源稳定键连接真实 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- Doris FE 版本：`{', '.join(report['doris_versions'])}`",
        f"- MySQL 协议兼容版本：`{report['mysql_protocol_version']}`",
        f"- 最新交易日：`{report['latest_date']}`",
        f"- 行集哈希一致：`{report['matched']}/{report['total']}`",
        "",
        "| 场景 | 资源数 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| {item['name']} | {len(item['resources'])} | {item['expected_count']} | "
            f"{item['actual_count']} | {'是' if item['matched'] else '否'} | {item['p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "> reference SQL 由人工定义的关系连接模板生成，只使用 catalog 声明的稳定键；编译器 SQL 独立经过 ANTLR/Typed AST/Logical IR/Physical IR/SQLGlot 路径生成。两侧均在同一 Doris 数据快照执行，并比较排序无关的完整结果行集 SHA-256。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
