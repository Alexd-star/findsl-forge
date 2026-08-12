from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from findsl.official.backend.diff import hash_result_rows
from findsl.official.backend.executor import (
    DorisExecutionConfig,
    execute_doris_explain,
    execute_doris_query,
)
from findsl.official.context import CompileContext
from findsl.official.pipeline import compile_official


FIXTURE_SNAPSHOT = "findsl-group-oracle-2026-04-14-v1"
FIXTURE_GROUP = "ORACLE_GROUP_001"
FIXTURE_ROWS = (
    (0, "000001"),
    (0, "000002"),
)


def collect(
    repo_root: Path,
    doris: DorisExecutionConfig,
) -> dict:
    _mutate(doris, _delete_sql())
    _mutate(doris, _insert_sql())
    try:
        with tempfile.TemporaryDirectory(prefix="findsl-group-evidence-") as temp:
            context = _fixture_context(repo_root, Path(temp))
            cases = (
                (
                    "group_volume_sum",
                    "indicator('', '', '成交量', '今日', '行业', '', '') > 0",
                    _reference_sql("SUM(q.volume)"),
                ),
                (
                    "group_float_cap_weighted_return",
                    "indicator('', '', '涨幅', '今日', '行业', '', '') > -100",
                    _reference_sql(
                        "SUM((q.lastPx-q.preClosePx)*q.listedShare) / "
                        "NULLIF(SUM(q.preClosePx*q.listedShare),0) * 100.0"
                    ),
                ),
            )
            results = []
            for case_id, source, reference_sql in cases:
                compiled = compile_official(source, context=context)
                generated = execute_doris_query(doris, compiled.backend["sql"])
                reference = execute_doris_query(doris, reference_sql)
                explain = execute_doris_explain(doris, compiled.backend["sql"])
                matched = generated.rows == reference.rows
                results.append(
                    {
                        "case_id": case_id,
                        "source": source,
                        "selected_strategy": compiled.physical["selected_strategy"],
                        "generated_sql": compiled.backend["sql"],
                        "reference_sql": reference_sql,
                        "generated_rows": [list(row) for row in generated.rows],
                        "reference_rows": [list(row) for row in reference.rows],
                        "generated_hash": generated.ordered_hash,
                        "reference_hash": reference.ordered_hash,
                        "row_count": len(generated.rows),
                        "matched": matched,
                        "elapsed_ms": generated.elapsed_ms,
                        "reference_elapsed_ms": reference.elapsed_ms,
                        "explain_contains_membership_join": (
                            "scope_membership" in explain.text
                        ),
                    }
                )
    finally:
        _mutate(doris, _delete_sql())
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "git_head": _git_head(repo_root),
        "fixture_snapshot_id": FIXTURE_SNAPSHOT,
        "fixture_group_code": FIXTURE_GROUP,
        "fixture_members": [list(row) for row in FIXTURE_ROWS],
        "fixture_cleaned": _fixture_count(doris) == 0,
        "cases": results,
        "passed": all(
            item["matched"]
            and item["row_count"] == 1
            and item["explain_contains_membership_join"]
            for item in results
        ),
        "generated_result_hash": hash_result_rows(
            tuple(
                (
                    item["case_id"],
                    item["generated_hash"],
                    str(item["row_count"]),
                )
                for item in results
            ),
            ordered=True,
        ),
    }


def _fixture_context(repo_root: Path, temp_root: Path) -> CompileContext:
    shutil.copytree(repo_root / "configs", temp_root / "configs")
    runtime_path = temp_root / "configs/official/external_scope_runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["entries"] = [
        {
            "scope_type": "industry",
            "scope_code": FIXTURE_GROUP,
            "scope_name": "群组真值实验",
            "alias": "群组真值实验",
            "normalized_alias": "群组真值实验",
            "source": "eastmoney",
            "as_of_date": "2026-04-14",
            "snapshot_id": FIXTURE_SNAPSHOT,
        }
    ]
    runtime_path.write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return CompileContext.load(temp_root)


def _reference_sql(metric: str) -> str:
    return f"""
SELECT
  m.scope_type AS group_type,
  m.scope_code AS group_code,
  m.scope_name AS group_name,
  q.bizdate,
  {metric} AS metric_value,
  COUNT(DISTINCT CONCAT(q.mktcode, ':', q.tgtcode)) AS member_count,
  COUNT(DISTINCT CONCAT(q.mktcode, ':', q.tgtcode)) AS metric_member_count
FROM newzl.hsj_stock_hq_basic q
INNER JOIN findsl_ext.scope_membership m
  ON q.mktcode=m.mktcode AND q.tgtcode=m.tgtcode
WHERE q.bizdate='2026-04-14'
  AND m.snapshot_id='{FIXTURE_SNAPSHOT}'
  AND m.scope_type='industry'
  AND m.scope_code='{FIXTURE_GROUP}'
  AND (m.effective_from IS NULL OR m.effective_from<=q.bizdate)
  AND (m.effective_to IS NULL OR m.effective_to>=q.bizdate)
GROUP BY m.scope_type,m.scope_code,m.scope_name,q.bizdate
HAVING COUNT(DISTINCT CONCAT(q.mktcode, ':', q.tgtcode))>=2
""".strip()


def _insert_sql() -> str:
    values = ",".join(
        "(" + ",".join(
            (
                f"'{FIXTURE_SNAPSHOT}'",
                f"'{FIXTURE_GROUP}'",
                str(market),
                f"'{code}'",
                "'industry'",
                "'群组真值实验'",
                "'2026-04-14'",
                "NULL",
                "NULL",
            )
        ) + ")"
        for market, code in FIXTURE_ROWS
    )
    return (
        "INSERT INTO findsl_ext.scope_membership "
        "(snapshot_id,scope_code,mktcode,tgtcode,scope_type,scope_name,"
        "effective_from,effective_to,weight) VALUES "
        + values
    )


def _delete_sql() -> str:
    return (
        "DELETE FROM findsl_ext.scope_membership "
        f"WHERE snapshot_id='{FIXTURE_SNAPSHOT}'"
    )


def _mutate(config: DorisExecutionConfig, sql: str) -> None:
    command = [
        config.mysql_executable,
        "--batch",
        "--raw",
        "--default-character-set=utf8mb4",
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--user",
        config.user,
        "--database",
        config.database,
        "--execute",
        sql,
    ]
    environment = os.environ.copy()
    if config.password:
        environment["MYSQL_PWD"] = config.password
    subprocess.run(
        command,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=config.timeout_seconds,
        check=True,
    )


def _fixture_count(config: DorisExecutionConfig) -> int:
    result = execute_doris_query(
        config,
        "SELECT COUNT(*) FROM findsl_ext.scope_membership "
        f"WHERE snapshot_id='{FIXTURE_SNAPSHOT}'",
    )
    return int(result.rows[0][0])


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "<unknown>"


def render_markdown(report: dict) -> str:
    lines = [
        "# 群组结果实体 Doris 真值证据",
        "",
        f"- 状态：`{'PASS' if report['passed'] else 'FAIL'}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 隔离快照：`{report['fixture_snapshot_id']}`",
        f"- 实验后清理：`{report['fixture_cleaned']}`",
        "",
        "| 用例 | 生成结果 | Reference 结果 | 完整行集一致 | EXPLAIN 成员表 |",
        "|---|---:|---:|---|---|",
    ]
    for item in report["cases"]:
        lines.append(
            f"| `{item['case_id']}` | {item['row_count']} | "
            f"{len(item['reference_rows'])} | `{item['matched']}` | "
            f"`{item['explain_contains_membership_join']}` |"
        )
    lines.extend(
        [
            "",
            "> 该证据使用独立两只证券成员夹具，仅用于验证群组计划和聚合公式；"
            "它不会被计入公开数据快照，实验结束后自动删除。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--database", default="newzl")
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
        ),
    )
    Path(args.json_output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path(args.report_output).write_text(render_markdown(report), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
