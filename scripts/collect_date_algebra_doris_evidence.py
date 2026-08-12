from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from findsl.official.backend.executor import (
    DorisExecutionConfig,
    execute_doris_explain,
    execute_doris_query,
)
from findsl.official.pipeline import compile_official


TABLE = "newzl.hsj_stock_hq_basic"


def collect(repo_root: Path, doris: DorisExecutionConfig) -> dict:
    cases = (
        (
            "calendar_week_ago",
            "indicator('', '', '成交量', '一周前', '', '', '') > 0",
            f"""
WITH anchor AS (SELECT MAX(bizdate) AS d FROM {TABLE}),
target AS (
  SELECT MAX(q.bizdate) AS d
  FROM {TABLE} q CROSS JOIN anchor a
  WHERE q.bizdate <= DATE_SUB(a.d, INTERVAL 1 WEEK)
)
SELECT q.mktcode,q.tgtcode,q.bizdate
FROM {TABLE} q CROSS JOIN target t
WHERE q.volume > 0 AND q.bizdate=t.d
""".strip(),
        ),
        (
            "previous_session_before_explicit_date",
            "indicator('', '', '成交量', '2025年5月6日的前1日', '', '', '') > 0",
            f"""
WITH target AS (
  SELECT MAX(bizdate) AS d FROM {TABLE} WHERE bizdate < '2025-05-06'
)
SELECT q.mktcode,q.tgtcode,q.bizdate
FROM {TABLE} q CROSS JOIN target t
WHERE q.volume > 0 AND q.bizdate=t.d
""".strip(),
        ),
        (
            "previous_week_last_session",
            "indicator('', '', '成交量', '上周五最后一个交易日', '', '', '') > 0",
            f"""
WITH anchor AS (SELECT MAX(bizdate) AS d FROM {TABLE}),
target AS (
  SELECT MAX(q.bizdate) AS d
  FROM {TABLE} q CROSS JOIN anchor a
  WHERE q.bizdate <= DATE_SUB(DATE_TRUNC(a.d, 'WEEK'), INTERVAL 1 DAY)
)
SELECT q.mktcode,q.tgtcode,q.bizdate
FROM {TABLE} q CROSS JOIN target t
WHERE q.volume > 0 AND q.bizdate=t.d
""".strip(),
        ),
        (
            "current_month_anchor_day",
            "indicator('', '', '成交量', '本月13日', '', '', '') > 0",
            f"""
WITH anchor AS (SELECT MAX(bizdate) AS d FROM {TABLE}),
target AS (
  SELECT DATE_ADD(DATE_TRUNC(d, 'MONTH'), INTERVAL 12 DAY) AS d FROM anchor
)
SELECT q.mktcode,q.tgtcode,q.bizdate
FROM {TABLE} q CROSS JOIN target t
WHERE q.volume > 0 AND q.bizdate=t.d
""".strip(),
        ),
    )
    results = []
    for case_id, dsl, reference_sql in cases:
        compiled = compile_official(dsl)
        generated_sql = compiled.backend["sql"]
        generated = execute_doris_query(doris, generated_sql)
        reference = execute_doris_query(doris, reference_sql)
        explain = execute_doris_explain(doris, generated_sql)
        generated_rows = tuple(sorted(generated.rows))
        reference_rows = tuple(sorted(reference.rows))
        results.append(
            {
                "case_id": case_id,
                "dsl": dsl,
                "selected_strategy": compiled.physical["selected_strategy"],
                "generated_sql": generated_sql,
                "reference_sql": reference_sql,
                "generated_row_count": len(generated_rows),
                "reference_row_count": len(reference_rows),
                "generated_hash": generated.unordered_hash,
                "reference_hash": reference.unordered_hash,
                "row_set_matched": generated_rows == reference_rows,
                "generated_dates": sorted({row[2] for row in generated_rows}),
                "reference_dates": sorted({row[2] for row in reference_rows}),
                "elapsed_ms": generated.elapsed_ms,
                "reference_elapsed_ms": reference.elapsed_ms,
                "explain_contains_date_predicate": "bizdate" in explain.text,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "git_head": _git_head(repo_root),
        "database": doris.database,
        "case_count": len(results),
        "cases": results,
        "passed": all(
            item["row_set_matched"]
            and item["generated_row_count"] > 0
            and item["explain_contains_date_predicate"]
            for item in results
        ),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 日期代数 Doris 真值证据",
        "",
        f"- 状态：`{'PASS' if report['passed'] else 'FAIL'}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 用例数：`{report['case_count']}`",
        "",
        "| 用例 | 生成结果行数 | Reference 行数 | 日期集合 | 完整行集一致 | EXPLAIN 日期谓词 |",
        "|---|---:|---:|---|---|---|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['case_id']}` | {item['generated_row_count']} | "
            f"{item['reference_row_count']} | `{','.join(item['generated_dates'])}` | "
            f"`{item['row_set_matched']}` | "
            f"`{item['explain_contains_date_predicate']}` |"
        )
    lines.extend(
        [
            "",
            "> Reference SQL 独立描述交易日边界，不复用编译器生成的日期表达式；"
            "比较对象为完整无序结果集，而非抽样行。",
        ]
    )
    return "\n".join(lines) + "\n"


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "<unknown>"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--report-output", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = collect(
        root,
        DorisExecutionConfig(
            args.host,
            args.port,
            args.user,
            args.password,
            args.database,
            args.client,
        ),
    )
    Path(args.json_output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.report_output).write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
