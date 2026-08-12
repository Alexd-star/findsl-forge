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
FIXTURE_GROUPS = {
    "ORACLE_GROUP_001": ((0, "000001"), (0, "000002")),
    "ORACLE_GROUP_002": ((0, "000004"), (0, "000006")),
}


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
                    "indicator('', '群组真值实验甲', '成交量', '今日', '行业', '', '') > 0",
                    _reference_sql("SUM(q.volume)", "ORACLE_GROUP_001"),
                    1,
                ),
                (
                    "group_float_cap_weighted_return",
                    "indicator('', '群组真值实验甲', '涨幅', '今日', '行业', '', '') > -100",
                    _reference_sql(
                        "SUM((q.lastPx-q.preClosePx)*q.listedShare) / "
                        "NULLIF(SUM(q.preClosePx*q.listedShare),0) * 100.0",
                        "ORACLE_GROUP_001",
                    ),
                    1,
                ),
                (
                    "group_metric_intersection",
                    "indicator('', '', '成交量', '今日', '行业', '', '') > 100000000 "
                    "and indicator('', '', '总股本', '今日', '行业', '', '') > 5000000000",
                    _group_key_reference("ORACLE_GROUP_001"),
                    1,
                ),
                (
                    "group_stage_candidate_rank",
                    "indicator('', '', '成交量', '今日', '行业', '', '') < 100000000 "
                    "then rank('', '', '成交量', 'desc', '今日', '行业', '', '') = 1",
                    _reference_sql("SUM(q.volume)", "ORACLE_GROUP_002"),
                    1,
                ),
                (
                    "group_consecutive_trading_sessions",
                    "indicator('', '', '成交量', '近3日', '行业', '', "
                    "'CONS=2日') > 100000000",
                    _temporal_reference_sql(),
                    1,
                ),
                (
                    "group_exist_zero_hit_preserved",
                    "indicator('', '', '成交量', '近3日', '行业', '', "
                    "'EXIST<2日') > 100000000",
                    _temporal_zero_hit_reference_sql(),
                    1,
                ),
            )
            results = []
            for case_id, source, reference_sql, expected_row_count in cases:
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
                        "expected_row_count": expected_row_count,
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
        "fixture_groups": {
            group_code: [list(row) for row in rows]
            for group_code, rows in FIXTURE_GROUPS.items()
        },
        "fixture_cleaned": _fixture_count(doris) == 0,
        "cases": results,
        "passed": all(
            item["matched"]
            and item["row_count"] == item["expected_row_count"]
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
            "scope_code": group_code,
            "scope_name": f"群组真值实验{name}",
            "alias": f"群组真值实验{name}",
            "normalized_alias": f"群组真值实验{name}",
            "source": "eastmoney",
            "as_of_date": "2026-04-14",
            "snapshot_id": FIXTURE_SNAPSHOT,
        }
        for group_code, name in zip(FIXTURE_GROUPS, ("甲", "乙"))
    ]
    runtime_path.write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return CompileContext.load(temp_root)


def _reference_sql(metric: str, group_code: str) -> str:
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
  AND m.scope_code='{group_code}'
  AND (m.effective_from IS NULL OR m.effective_from<=q.bizdate)
  AND (m.effective_to IS NULL OR m.effective_to>=q.bizdate)
GROUP BY m.scope_type,m.scope_code,m.scope_name,q.bizdate
HAVING COUNT(DISTINCT CONCAT(q.mktcode, ':', q.tgtcode))>=2
""".strip()


def _group_key_reference(group_code: str) -> str:
    return f"""
SELECT DISTINCT
  m.scope_type AS group_type,
  m.scope_code AS group_code,
  m.scope_name AS group_name,
  q.bizdate
FROM newzl.hsj_stock_hq_basic q
INNER JOIN findsl_ext.scope_membership m
  ON q.mktcode=m.mktcode AND q.tgtcode=m.tgtcode
WHERE q.bizdate='2026-04-14'
  AND m.snapshot_id='{FIXTURE_SNAPSHOT}'
  AND m.scope_type='industry'
  AND m.scope_code='{group_code}'
  AND (m.effective_from IS NULL OR m.effective_from<=q.bizdate)
  AND (m.effective_to IS NULL OR m.effective_to>=q.bizdate)
""".strip()


def _temporal_reference_sql() -> str:
    return f"""
WITH latest_dates AS (
  SELECT bizdate
  FROM (SELECT DISTINCT bizdate FROM newzl.hsj_stock_hq_basic) dates
  ORDER BY bizdate DESC
  LIMIT 3
),
calendar AS (
  SELECT
    bizdate,
    DENSE_RANK() OVER (ORDER BY bizdate) AS session_seq
  FROM (SELECT DISTINCT bizdate FROM newzl.hsj_stock_hq_basic) dates
),
daily AS (
  SELECT
    m.scope_type AS group_type,
    m.scope_code AS group_code,
    m.scope_name AS group_name,
    q.bizdate,
    SUM(q.volume) AS metric_value
  FROM newzl.hsj_stock_hq_basic q
  INNER JOIN latest_dates d ON q.bizdate=d.bizdate
  INNER JOIN findsl_ext.scope_membership m
    ON q.mktcode=m.mktcode AND q.tgtcode=m.tgtcode
  WHERE m.snapshot_id='{FIXTURE_SNAPSHOT}'
    AND m.scope_type='industry'
    AND (m.effective_from IS NULL OR m.effective_from<=q.bizdate)
    AND (m.effective_to IS NULL OR m.effective_to>=q.bizdate)
  GROUP BY m.scope_type,m.scope_code,m.scope_name,q.bizdate
  HAVING COUNT(DISTINCT CONCAT(q.mktcode, ':', q.tgtcode))>=2
),
hits AS (
  SELECT d.*, c.session_seq
  FROM daily d
  INNER JOIN calendar c ON d.bizdate=c.bizdate
  WHERE d.metric_value>100000000
),
numbered AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY group_type,group_code ORDER BY bizdate
    ) AS hit_seq
  FROM hits
),
runs AS (
  SELECT
    group_type,group_code,group_name,
    COUNT(*) AS run_length
  FROM numbered
  GROUP BY group_type,group_code,group_name,session_seq-hit_seq
),
metrics AS (
  SELECT
    group_type,group_code,group_name,
    MAX(run_length) AS metric_value
  FROM runs
  GROUP BY group_type,group_code,group_name
)
SELECT
  group_type,group_code,group_name,
  (SELECT MAX(bizdate) FROM newzl.hsj_stock_hq_basic) AS bizdate,
  metric_value
FROM metrics
WHERE metric_value>=2
""".strip()


def _temporal_zero_hit_reference_sql() -> str:
    return f"""
WITH latest_dates AS (
  SELECT bizdate
  FROM (SELECT DISTINCT bizdate FROM newzl.hsj_stock_hq_basic) dates
  ORDER BY bizdate DESC
  LIMIT 3
),
daily AS (
  SELECT
    m.scope_type AS group_type,
    m.scope_code AS group_code,
    m.scope_name AS group_name,
    q.bizdate,
    SUM(q.volume) AS daily_volume
  FROM newzl.hsj_stock_hq_basic q
  INNER JOIN latest_dates d ON q.bizdate=d.bizdate
  INNER JOIN findsl_ext.scope_membership m
    ON q.mktcode=m.mktcode AND q.tgtcode=m.tgtcode
  WHERE m.snapshot_id='{FIXTURE_SNAPSHOT}'
    AND m.scope_type='industry'
    AND (m.effective_from IS NULL OR m.effective_from<=q.bizdate)
    AND (m.effective_to IS NULL OR m.effective_to>=q.bizdate)
  GROUP BY m.scope_type,m.scope_code,m.scope_name,q.bizdate
  HAVING COUNT(DISTINCT CONCAT(q.mktcode, ':', q.tgtcode))>=2
),
metrics AS (
  SELECT
    group_type,group_code,group_name,
    SUM(CASE WHEN daily_volume>100000000 THEN 1 ELSE 0 END) AS metric_value
  FROM daily
  GROUP BY group_type,group_code,group_name
)
SELECT
  group_type,group_code,group_name,
  (SELECT MAX(bizdate) FROM newzl.hsj_stock_hq_basic) AS bizdate,
  metric_value
FROM metrics
WHERE metric_value<2
""".strip()


def _insert_sql() -> str:
    values = ",".join(
        "(" + ",".join(
            (
                f"'{FIXTURE_SNAPSHOT}'",
                f"'{group_code}'",
                str(market),
                f"'{code}'",
                "'industry'",
                f"'群组真值实验{name}'",
                "'2005-01-01'",
                "NULL",
                "NULL",
            )
        ) + ")"
        for (group_code, rows), name in zip(
            FIXTURE_GROUPS.items(), ("甲", "乙")
        )
        for market, code in rows
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
            "> 该证据使用两个隔离群组夹具，用于验证群组计划、聚合公式、集合运算和候选集阶段排名；"
            "它不会被计入公开数据快照，实验结束后自动删除。连续条件按真实交易日序列计算，"
            "周末不会被误判为中断。",
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
