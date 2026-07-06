from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Mapping, Optional


def build_official_performance_matrix(evidence: Mapping[str, Any]) -> Dict[str, Any]:
    queries = [_query_row(item) for item in evidence.get("queries", [])]
    p95_values = [row["p95_ms"] for row in queries if row["p95_ms"] is not None]
    avg_values = [row["avg_ms"] for row in queries if row["avg_ms"] is not None]
    summary = {
        "generated_at": evidence.get("generated_at", ""),
        "query_count": len(queries),
        "all_queries_under_10s": bool(queries) and all(row["execution_target"] == "PASS" for row in queries),
        "max_p95_ms": round(max(p95_values), 3) if p95_values else None,
        "mean_avg_ms": round(mean(avg_values), 3) if avg_values else None,
        "prefix_query_count": sum(1 for row in queries if row["plan_kind"] == "prefix"),
        "window_query_count": sum(1 for row in queries if row["plan_kind"] == "window"),
        "baseline_prefix_row_count_match": bool(evidence.get("baseline_prefix_row_count_match")),
        "baseline_vs_prefix_speedup": evidence.get("baseline_vs_prefix_speedup"),
        "row_counts": dict(evidence.get("row_counts", {})),
    }
    return {"summary": summary, "queries": queries}


def write_official_performance_matrix(
    *,
    evidence_path: Path,
    json_output: Optional[Path] = None,
    report_output: Optional[Path] = None,
) -> Dict[str, Any]:
    evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    matrix = build_official_performance_matrix(evidence)
    if json_output:
        Path(json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(json_output).write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    if report_output:
        Path(report_output).parent.mkdir(parents=True, exist_ok=True)
        Path(report_output).write_text(_render_markdown(matrix), encoding="utf-8")
    return matrix


def _query_row(item: Mapping[str, Any]) -> Dict[str, Any]:
    avg_ms = _round_or_none(item.get("avg_ms"))
    p95_ms = _round_or_none(item.get("p95_ms"))
    plan_kind = _plan_kind(item)
    execution_target = "PASS" if p95_ms is not None and p95_ms <= 10000 else "FAIL"
    return {
        "name": str(item.get("name", "")),
        "row_count": int(item.get("row_count", 0)),
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "plan_kind": plan_kind,
        "execution_target": execution_target,
        "plan_contains_prefix": bool(item.get("plan_contains_prefix")),
        "plan_contains_window": bool(item.get("plan_contains_window")),
        "sql_preview": str(item.get("sql", ""))[:240],
    }


def _plan_kind(item: Mapping[str, Any]) -> str:
    if item.get("plan_contains_prefix"):
        return "prefix"
    if item.get("plan_contains_window"):
        return "window"
    return "ordinary"


def _round_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 3)


def _render_markdown(matrix: Mapping[str, Any]) -> str:
    summary = matrix["summary"]
    lines = [
        "# 官方真实数据逐问句性能矩阵",
        "",
        "本文由 `reports/official_doris_evidence.json` 生成，只汇总已经在本地 Apache Doris 上真实执行并记录行数、耗时和 EXPLAIN 标记的查询。它用于补充赛题中“SQL 执行筛选结果不高于 10s”的逐问句证据，不替代原始 Doris evidence。",
        "",
        "## 摘要",
        "",
        f"- Doris evidence 生成时间：`{summary.get('generated_at') or '<unknown>'}`",
        f"- 查询数量：{summary['query_count']}",
        f"- 全部查询 P95 <= 10s：{summary['all_queries_under_10s']}",
        f"- 最大 P95：{summary['max_p95_ms']} ms",
        f"- 平均 Avg：{summary['mean_avg_ms']} ms",
        f"- baseline/prefix 行数一致：{summary['baseline_prefix_row_count_match']}",
        f"- baseline vs prefix speedup：{summary['baseline_vs_prefix_speedup']}x",
        "",
        "## 官方三表行数",
        "",
        "| 表名 | 行数 |",
        "|---|---:|",
    ]
    for table, count in summary.get("row_counts", {}).items():
        lines.append(f"| {table} | {count} |")
    lines.extend(
        [
            "",
            "## 逐问句性能矩阵",
            "",
            "| Query | Rows | Avg ms | P95 ms | Plan | 10s Target |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for row in matrix["queries"]:
        lines.append(
            f"| {row['name']} | {row['row_count']} | {row['avg_ms']} | {row['p95_ms']} | "
            f"{row['plan_kind']} | {row['execution_target']} |"
        )
    lines.extend(
        [
            "",
            "## 解释口径",
            "",
            "- `ordinary` 表示普通过滤或 join 查询，没有显式窗口或 prefix 表。",
            "- `window` 表示 EXPLAIN 或 SQL 中出现窗口执行路径，可作为 baseline 或排名类查询证据。",
            "- `prefix` 表示 SQL/EXPLAIN 使用官方 prefix 特征表，是长窗口优化路径证据。",
            "- `10s Target` 仅说明该条 evidence 中记录的 P95 是否低于赛题 10 秒目标；最终答辩仍应保留原始 SQL、EXPLAIN 和 JSON 作为审计来源。",
            "",
        ]
    )
    return "\n".join(lines)
