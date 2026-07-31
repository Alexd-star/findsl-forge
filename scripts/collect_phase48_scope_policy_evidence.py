from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from findsl.official.external.policy import ScopeSemanticPolicy
from findsl.official.external.runtime import default_external_scope_catalog
from findsl.official.pipeline import compile_official


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect independent Phase 48 scope-policy Doris evidence"
    )
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--compile-repeats", type=int, default=20)
    parser.add_argument("--compile-target-ms", type=float, default=50.0)
    parser.add_argument("--performance-target-ms", type=float, default=10_000.0)
    parser.add_argument(
        "--json-output",
        default="reports/phase48_scope_semantic_policy_doris.json",
    )
    parser.add_argument(
        "--report-output",
        default="reports/phase48_scope_semantic_policy_doris.md",
    )
    args = parser.parse_args()
    if args.repeats <= 0 or args.compile_repeats <= 0:
        parser.error("repeat counts must be positive")

    runtime = default_external_scope_catalog()
    if runtime.semantic_policies is None:
        raise RuntimeError("scope semantic policy catalog is unavailable")
    basic = f"`{args.database}`.`hsj_stock_hq_basic`"
    latest = _query_rows(args, f"SELECT MAX(bizdate) FROM {basic}")[0][0]
    cases = []
    for policy in runtime.semantic_policies.policies:
        resolved = runtime.resolve(policy.aliases[0])
        reference_members_sql = _reference_members_sql(policy)
        materialized_sql = (
            "SELECT mktcode,tgtcode FROM `findsl_ext`.`scope_membership` "
            f"WHERE snapshot_id={_literal(resolved.option.snapshot_id)} "
            f"AND scope_code={_literal(resolved.option.scope_code)}"
        )
        expected_members = {
            tuple(row[:2]) for row in _query_rows(args, reference_members_sql)
        }
        materialized_members = {
            tuple(row[:2]) for row in _query_rows(args, materialized_sql)
        }
        source = (
            f"indicator('', '{policy.aliases[0]}', '', '', '', '', '') = 'all'"
        )
        compile_timings = []
        compiled = None
        for _ in range(args.compile_repeats):
            started = time.perf_counter_ns()
            compiled = compile_official(source)
            compile_timings.append(
                round((time.perf_counter_ns() - started) / 1_000_000, 4)
            )
        assert compiled is not None
        generated_sql = compiled.backend["sql"]
        reference_query = (
            "WITH reference_members AS ("
            f"{reference_members_sql}) "
            "SELECT q.mktcode,q.tgtcode,q.bizdate "
            f"FROM {basic} q INNER JOIN reference_members r "
            "ON r.mktcode=q.mktcode AND r.tgtcode=q.tgtcode "
            f"WHERE q.bizdate={_literal(latest)}"
        )
        expected_rows = {
            tuple(row[:3]) for row in _query_rows(args, reference_query)
        }
        actual_rows = set()
        execution_timings = []
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            actual_rows = {
                tuple(row[:3]) for row in _query_rows(args, generated_sql)
            }
            execution_timings.append(
                round((time.perf_counter_ns() - started) / 1_000_000, 4)
            )
        explain = "\n".join(
            "\t".join(row) for row in _query_rows(args, f"EXPLAIN {generated_sql}")
        )
        physical_json = json.dumps(
            compiled.physical["plan"],
            ensure_ascii=False,
            sort_keys=True,
        )
        compile_p95 = _nearest_rank(compile_timings, 0.95)
        execution_p95 = _nearest_rank(execution_timings, 0.95)
        materialization_matched = expected_members == materialized_members
        query_matched = expected_rows == actual_rows
        provenance_contract = all(
            fragment in physical_json
            for fragment in (
                policy.policy_id,
                policy.semantic_basis,
                policy.risk_level,
            )
        )
        sql_contract = all(
            fragment in generated_sql
            for fragment in (
                resolved.option.scope_code,
                resolved.option.snapshot_id,
            )
        )
        cases.append(
            {
                "policy_id": policy.policy_id,
                "alias": policy.aliases[0],
                "resolution_kind": policy.resolution_kind,
                "semantic_basis": policy.semantic_basis,
                "risk_level": policy.risk_level,
                "runtime_scope_code": resolved.option.scope_code,
                "runtime_snapshot_id": resolved.option.snapshot_id,
                "reference_members_sql": reference_members_sql,
                "materialized_members_sql": materialized_sql,
                "reference_query_sql": reference_query,
                "generated_sql": generated_sql,
                "source_member_count": len(expected_members),
                "materialized_member_count": len(materialized_members),
                "source_member_sha256": _row_hash(expected_members),
                "materialized_member_sha256": _row_hash(materialized_members),
                "materialization_matched": materialization_matched,
                "expected_count": len(expected_rows),
                "actual_count": len(actual_rows),
                "expected_sha256": _row_hash(expected_rows),
                "actual_sha256": _row_hash(actual_rows),
                "query_matched": query_matched,
                "missing_sample": sorted(expected_rows - actual_rows)[:10],
                "extra_sample": sorted(actual_rows - expected_rows)[:10],
                "compile_elapsed_ms": compile_timings,
                "compile_p95_ms": compile_p95,
                "compile_under_target": compile_p95 < args.compile_target_ms,
                "execution_elapsed_ms": execution_timings,
                "execution_p95_ms": execution_p95,
                "execution_under_target": execution_p95
                < args.performance_target_ms,
                "provenance_contract": provenance_contract,
                "sql_contract": sql_contract,
                "explain_sha256": hashlib.sha256(
                    explain.encode("utf-8")
                ).hexdigest(),
                "explain_excerpt": "\n".join(explain.splitlines()[:80]),
            }
        )

    passed = bool(cases) and all(
        item["materialization_matched"]
        and item["query_matched"]
        and item["compile_under_target"]
        and item["execution_under_target"]
        and item["provenance_contract"]
        and item["sql_contract"]
        for item in cases
    )
    report = {
        "schema_version": 1,
        "git_head": _git_head(),
        "policy_set_id": runtime.semantic_policies.policy_set_id,
        "policy_profile": runtime.semantic_policies.profile,
        "latest_data_date": latest,
        "repeats": args.repeats,
        "compile_repeats": args.compile_repeats,
        "compile_target_ms": args.compile_target_ms,
        "performance_target_ms": args.performance_target_ms,
        "status": "PASS" if passed else "FAIL",
        "total": len(cases),
        "materialization_matched": sum(
            item["materialization_matched"] for item in cases
        ),
        "query_matched": sum(item["query_matched"] for item in cases),
        "compile_passed": sum(item["compile_under_target"] for item in cases),
        "execution_passed": sum(item["execution_under_target"] for item in cases),
        "provenance_passed": sum(
            item["provenance_contract"] and item["sql_contract"] for item in cases
        ),
        "cases": cases,
    }
    _write_report(report, Path(args.json_output), Path(args.report_output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _reference_members_sql(policy: ScopeSemanticPolicy) -> str:
    if policy.resolution_kind == "exact_scope":
        return (
            "SELECT mktcode,tgtcode FROM `findsl_ext`.`scope_membership` "
            f"WHERE snapshot_id={_literal(policy.source_snapshot_id)} "
            f"AND scope_code={_literal(policy.target_scope_code)}"
        )
    if policy.resolution_kind == "security_name_regex":
        if policy.selector_pattern != "^S(?!T)":
            raise ValueError(
                f"no independent SQL rule for selector: {policy.policy_id}"
            )
        return (
            "SELECT mktcode,tgtcode FROM `findsl_ext`.`scope_membership` "
            f"WHERE snapshot_id={_literal(policy.source_snapshot_id)} "
            "AND scope_type='security' AND scope_name LIKE 'S%' "
            "AND scope_name NOT LIKE 'ST%'"
        )
    component_queries = [
        "SELECT mktcode,tgtcode FROM `findsl_ext`.`scope_membership` "
        f"WHERE snapshot_id={_literal(component.source_snapshot_id)} "
        f"AND scope_code={_literal(component.scope_code)}"
        for component in policy.components
    ]
    operator = " INTERSECT " if policy.operation == "intersection" else " UNION "
    return operator.join(component_queries)


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


def _literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


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
        check=True,
    )
    return result.stdout.strip()


def _write_report(report, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Phase 48 范围语义政策独立 Doris 证据",
        "",
        f"- 状态：`{report['status']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 政策集：`{report['policy_set_id']}`",
        f"- 数据锚点：`{report['latest_data_date']}`",
        f"- 源成员与物化成员完整集合一致：`{report['materialization_matched']}/{report['total']}`",
        f"- 独立参考 SQL 与生成 SQL 完整行集一致：`{report['query_matched']}/{report['total']}`",
        f"- 编译 P95 < {report['compile_target_ms']:.0f} ms：`{report['compile_passed']}/{report['total']}`",
        f"- 执行 P95 < {report['performance_target_ms']:.0f} ms：`{report['execution_passed']}/{report['total']}`",
        f"- Physical IR 与 SQL 溯源合同：`{report['provenance_passed']}/{report['total']}`",
        "",
        "| 政策 | 源成员 | 物化成员 | 查询行数 | 编译P95/ms | 执行P95/ms | 状态 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["cases"]:
        case_passed = all(
            (
                item["materialization_matched"],
                item["query_matched"],
                item["compile_under_target"],
                item["execution_under_target"],
                item["provenance_contract"],
                item["sql_contract"],
            )
        )
        lines.append(
            f"| `{item['policy_id']}` | {item['source_member_count']} | "
            f"{item['materialized_member_count']} | {item['actual_count']} | "
            f"{item['compile_p95_ms']:.4f} | {item['execution_p95_ms']:.4f} | "
            f"{'PASS' if case_passed else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "> 参考 SQL 直接读取原始来源快照：精确范围按源快照与源代码筛选，S 板按证券简称规则筛选，上海水利工程按两个完整集合求交。参考 SQL 未复用编译器生成 SQL，也未以行数相同替代完整稳定键集合比较。",
            "",
            "> 中等风险政策是比赛配置中的可替换业务口径，不冒充赛题方唯一语义；Physical IR 保留 policy_id、依据类型、风险等级和依据链接，SQL 只消费版本化成员快照。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
