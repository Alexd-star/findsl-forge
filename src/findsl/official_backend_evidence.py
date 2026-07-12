from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Dict, Iterable, List

import sqlglot
from sqlglot import exp

from .official.backend.doris import render_doris
from .official.backend.diff import compare_doris_sql
from .official.backend.executor import execute_doris_query_digest
from .official.lowering import lower_official_ast
from .official.physical.catalog import default_physical_catalog
from .official.physical.expressions import default_physical_expressions
from .official.physical.planner import plan_physical
from .official.physical.statistics import default_physical_statistics
from .official.physical.strategies import default_physical_strategies
from .official.registry import default_official_registry
from .official.semantics import OfficialSemanticAnalyzer
from .official_slot import _resolve_indicator_meta, parse_official_slot_with_diagnostics


def audit_official_backend_sources(
    sources: Iterable[str],
    sample_size: int = 20,
    *,
    baseline_gate: Dict[str, Any] = None,
    structural_diff: Dict[str, Any] = None,
    real_doris_execution: Dict[str, Any] = None,
    legacy_compiler=None,
) -> Dict[str, Any]:
    analyzer = OfficialSemanticAnalyzer(_resolve_indicator_meta)
    registry = default_official_registry()
    catalog = default_physical_catalog()
    expression_registry = default_physical_expressions(catalog)
    statistics = default_physical_statistics(catalog)
    strategies = default_physical_strategies(catalog)
    typed_ok = logical_ok = physical_ok = sqlglot_ok = safety_ok = 0
    errors: Counter[str] = Counter()
    resources: Counter[str] = Counter()
    latencies: List[int] = []
    samples = []
    structural_compared = structural_equivalent = structural_errors = 0
    structural_differences: Counter[str] = Counter()
    eligible_queries = []
    source_list = [str(source) for source in sources]

    for row_index, source in enumerate(source_list, start=2):
        started = perf_counter_ns()
        stage = "parse"
        try:
            parsed = parse_official_slot_with_diagnostics(source, mode="strict", frontend="antlr")
            stage = "typed"
            typed = analyzer.analyze(parsed.ast)
            typed_ok += 1
            stage = "logical"
            logical = lower_official_ast(typed, strict=True, domain_registry=registry)
            logical_ok += 1
            stage = "physical"
            physical = plan_physical(
                logical,
                catalog,
                statistics=statistics,
                strategies=strategies,
                expressions=expression_registry,
            )
            physical_ok += 1
            resources[physical.selected_resource] += 1
            stage = "sqlglot"
            rendered = render_doris(physical.plan, catalog, expression_registry)
            sqlglot_ok += int(rendered.round_trip_stable)
            safety_ok += int(rendered.validation.passed)
            if legacy_compiler is not None:
                try:
                    legacy = legacy_compiler.compile(source)
                    difference = compare_doris_sql(legacy.sql, rendered.sql)
                    structural_compared += 1
                    structural_equivalent += int(difference.equivalent)
                    structural_differences.update(difference.differences)
                    eligible_queries.append(
                        {
                            "excel_row": row_index,
                            "source": source,
                            "legacy_sql": legacy.sql,
                            "shadow_sql": rendered.sql,
                            "ordered": False,
                            "structural_differences": list(difference.differences),
                        }
                    )
                except Exception:
                    structural_errors += 1
        except Exception as exc:
            code = str(getattr(exc, "code", type(exc).__name__))
            errors[code] += 1
            if len(samples) < sample_size:
                samples.append({"excel_row": row_index, "stage": stage, "code": code, "message": str(exc)})
        finally:
            latencies.append(perf_counter_ns() - started)

    static_gate = (
        physical_ok > 0
        and physical_ok == sqlglot_ok == safety_ok
        and sum(errors.values()) + safety_ok == len(source_list)
    )
    structural_report = structural_diff
    if legacy_compiler is not None:
        structural_passed = structural_compared == safety_ok and structural_errors == 0
        structural_report = {
            "status": "PASS" if structural_passed else "FAIL",
            "passed": structural_passed,
            "eligible": safety_ok,
            "compared": structural_compared,
            "equivalent": structural_equivalent,
            "classified_differences": structural_compared - structural_equivalent,
            "difference_fields": dict(structural_differences.most_common()),
            "errors": structural_errors,
        }
    real_execution = real_doris_execution or {
        "status": "NOT_RUN",
        "reason": "Static backend audit does not imply execution or result equivalence on a live Doris cluster.",
    }
    gates = _phase5_gates(
        static_passed=static_gate,
        latency_p95_ms=_percentile(latencies, 0.95),
        baseline_gate=baseline_gate,
        structural_diff=structural_report,
        real_doris_execution=real_execution,
    )
    return {
        "schema_version": 1,
        "row_count": len(source_list),
        "typed_ok": typed_ok,
        "logical_ok": logical_ok,
        "physical_ok": physical_ok,
        "sqlglot_ok": sqlglot_ok,
        "safety_ok": safety_ok,
        "resources": dict(resources.most_common()),
        "errors": dict(errors.most_common()),
        "latency_ms": {"p50": _percentile(latencies, 0.50), "p95": _percentile(latencies, 0.95)},
        "samples": samples,
        "static_gate": {
            "passed": static_gate,
            "policy": "Every emitted SQL must round-trip in SQLGlot Doris dialect and pass the existing SELECT safety lint.",
        },
        "real_doris_execution": real_execution,
        "structural_diff": structural_report or {"status": "NOT_RUN", "passed": False},
        "eligible_queries": eligible_queries,
        "gates": gates,
    }


def _phase5_gates(
    *,
    static_passed: bool,
    latency_p95_ms: float,
    baseline_gate: Dict[str, Any] = None,
    structural_diff: Dict[str, Any] = None,
    real_doris_execution: Dict[str, Any] = None,
) -> Dict[str, Any]:
    baseline = baseline_gate or {"status": "NOT_EVALUATED", "passed": False}
    structural = structural_diff or {"status": "NOT_RUN", "passed": False}
    execution = real_doris_execution or {"status": "NOT_RUN"}
    execution_passed = execution.get("status") == "PASS" and bool(execution.get("passed"))
    gates = {
        "static_backend": {"status": "PASS" if static_passed else "FAIL", "passed": static_passed},
        "compile_latency": {
            "status": "PASS" if latency_p95_ms < 50.0 else "FAIL",
            "passed": latency_p95_ms < 50.0,
            "p95_ms": latency_p95_ms,
            "target_ms": 50.0,
        },
        "phase1_4_baseline": baseline,
        "structural_diff": structural,
        "real_doris_equivalence": {
            "status": execution.get("status", "NOT_RUN"),
            "passed": execution_passed,
        },
    }
    completion = all(
        gates[name].get("passed", False)
        for name in ("static_backend", "compile_latency", "phase1_4_baseline", "structural_diff", "real_doris_equivalence")
    )
    gates["phase5_completion"] = {"status": "PASS" if completion else "FAIL", "passed": completion}
    return gates


def build_official_backend_evidence(
    workbook: str,
    sample_size: int = 20,
    *,
    doris_config=None,
) -> Dict[str, Any]:
    import pandas as pd
    from .official_domain_evidence import build_official_domain_evidence
    from .official_slot import OfficialSlotCompiler

    path = Path(workbook).resolve()
    frame = pd.read_excel(path, sheet_name="训练语料", usecols=["slot_dsl"])
    domain_report = build_official_domain_evidence(str(path), sample_size=0)
    baseline_gate = _baseline_gate_from_domain_report(domain_report)
    report = audit_official_backend_sources(
        frame["slot_dsl"],
        sample_size=sample_size,
        baseline_gate=baseline_gate,
        legacy_compiler=OfficialSlotCompiler(mode="strict"),
    )
    if doris_config is not None:
        execution = execute_official_backend_equivalence(report["eligible_queries"], config=doris_config)
        report["real_doris_execution"] = execution
        report["gates"] = _phase5_gates(
            static_passed=report["static_gate"]["passed"],
            latency_p95_ms=report["latency_ms"]["p95"],
            baseline_gate=report["gates"]["phase1_4_baseline"],
            structural_diff=report["structural_diff"],
            real_doris_execution=execution,
        )
    report.update(
        {
            "workbook": str(path),
            "input_sha256": _file_sha256(path),
            "git_head": _git_head(),
        }
    )
    return report


def _baseline_gate_from_domain_report(report: Dict[str, Any]) -> Dict[str, Any]:
    passed = bool(report.get("gate", {}).get("passed"))
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "strict_parse_ok": int(report.get("strict_parse_ok", 0)),
        "strict_compile_ok": int(report.get("strict_compile_ok", 0)),
        "phase3_lowering_ok": int(report.get("phase3_lowering_ok", 0)),
        "domain_lowering_ok": int(report.get("domain_lowering_ok", 0)),
        "optimized_validated": int(report.get("optimized_validated", 0)),
    }


def execute_official_backend_equivalence(
    eligible_queries: Iterable[Dict[str, Any]],
    *,
    config,
    executor=execute_doris_query_digest,
) -> Dict[str, Any]:
    candidates = list(eligible_queries)
    results = []
    errors = 0
    matched = 0
    skipped_reasons = Counter()
    legacy_elapsed = []
    shadow_elapsed = []
    for candidate in candidates:
        item = {"excel_row": candidate["excel_row"], "source": candidate["source"]}
        reason = _nondeterministic_reason(candidate["legacy_sql"]) or _nondeterministic_reason(
            candidate["shadow_sql"]
        )
        if reason:
            skipped_reasons[reason] += 1
            item.update({"status": "SKIPPED", "reason": reason})
            results.append(item)
            continue
        try:
            legacy = executor(config, _stable_projection_query(candidate["legacy_sql"]))
            shadow = executor(config, _stable_projection_query(candidate["shadow_sql"]))
            ordered = bool(candidate.get("ordered"))
            legacy_rows, legacy_hash = _execution_digest(legacy, ordered)
            shadow_rows, shadow_hash = _execution_digest(shadow, ordered)
            row_counts_match = legacy_rows == shadow_rows
            hashes_match = legacy_hash == shadow_hash
            equivalent = row_counts_match and hashes_match
            matched += int(equivalent)
            legacy_elapsed.append(legacy.elapsed_ms)
            shadow_elapsed.append(shadow.elapsed_ms)
            item.update(
                {
                    "status": "PASS" if equivalent else "MISMATCH",
                    "ordered": ordered,
                    "legacy_rows": legacy_rows,
                    "shadow_rows": shadow_rows,
                    "legacy_hash": legacy_hash,
                    "shadow_hash": shadow_hash,
                    "legacy_elapsed_ms": round(legacy.elapsed_ms, 6),
                    "shadow_elapsed_ms": round(shadow.elapsed_ms, 6),
                }
            )
        except Exception as exc:
            errors += 1
            item.update({"status": "ERROR", "error": str(exc)})
        results.append(item)
    skipped = sum(skipped_reasons.values())
    deterministic_eligible = len(candidates) - skipped
    compared = deterministic_eligible - errors
    passed = (
        deterministic_eligible > 0
        and errors == 0
        and compared == deterministic_eligible
        and matched == deterministic_eligible
    )
    status = "PASS" if passed else ("NOT_EVALUATED" if deterministic_eligible == 0 else "FAIL")
    return {
        "status": status,
        "passed": passed,
        "eligible": len(candidates),
        "deterministic_eligible": deterministic_eligible,
        "compared": compared,
        "matched": matched,
        "mismatched": compared - matched,
        "errors": errors,
        "skipped": skipped,
        "skipped_reasons": dict(sorted(skipped_reasons.items())),
        "legacy_p95_ms": _percentile_float(legacy_elapsed, 0.95),
        "shadow_p95_ms": _percentile_float(shadow_elapsed, 0.95),
        "results": results,
    }


def _nondeterministic_reason(sql: str):
    statement = sqlglot.parse_one(sql, read="doris")
    if isinstance(statement, exp.Select) and statement.args.get("limit") is not None and statement.args.get("order") is None:
        return "NONDETERMINISTIC_LIMIT"
    return None


def _stable_projection_query(sql: str) -> str:
    statement = sqlglot.parse_one(sql, read="doris")
    if not isinstance(statement, exp.Select):
        raise ValueError("Doris equivalence requires a SELECT query")
    source = statement.subquery(alias="evidence_rows")
    query = exp.select(
        *(exp.column(name, table="evidence_rows", quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
    ).from_(source)
    query = query.order_by(
        *(exp.column(name, table="evidence_rows", quoted=True) for name in ("mktcode", "tgtcode", "bizdate"))
    )
    return query.sql(dialect="doris")


def _execution_digest(result, ordered: bool):
    if hasattr(result, "row_count") and hasattr(result, "sha256"):
        return result.row_count, result.sha256
    digest = result.ordered_hash if ordered else result.unordered_hash
    return len(result.rows), digest


def _percentile_float(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)], 6)


def write_official_backend_evidence(report: Dict[str, Any], json_output: str, markdown_output: str) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 5 Doris 物理后端官方证据", "",
        f"- 静态门禁：`{'PASS' if report['static_gate']['passed'] else 'FAIL'}`",
        f"- 官方问句：`{report['row_count']}`",
        f"- Typed AST：`{report['typed_ok']}`",
        f"- Logical IR：`{report['logical_ok']}`",
        f"- Physical IR：`{report['physical_ok']}`",
        f"- SQLGlot Doris round-trip：`{report['sqlglot_ok']}`",
        f"- 安全 lint：`{report['safety_ok']}`",
        f"- 端到端 P95：`{report['latency_ms']['p95']}` ms", "",
        "## 分层门禁", "", "| 门禁 | 状态 |", "|---|---|",
    ]
    lines.extend(f"| {name} | {gate.get('status', 'UNKNOWN')} |" for name, gate in report.get("gates", {}).items())
    execution = report.get("real_doris_execution", {})
    if execution.get("status") != "NOT_RUN":
        lines.extend([
            "", "## 真实 Doris 结果等价", "",
            "| 指标 | 数量/数值 |", "|---|---:|",
            f"| 静态候选 | {execution.get('eligible', 0)} |",
            f"| 确定性可比 | {execution.get('deterministic_eligible', 0)} |",
            f"| 实际比较 | {execution.get('compared', 0)} |",
            f"| 结果匹配 | {execution.get('matched', 0)} |",
            f"| 结果不匹配 | {execution.get('mismatched', 0)} |",
            f"| 跳过 | {execution.get('skipped', 0)} |",
            f"| 执行错误 | {execution.get('errors', 0)} |",
            f"| 旧后端 P95 | {execution.get('legacy_p95_ms', 0)} ms |",
            f"| 新后端 P95 | {execution.get('shadow_p95_ms', 0)} ms |",
            "",
            "> 无同层 ORDER BY 的 LIMIT 查询不具备可重复行集，按 NONDETERMINISTIC_LIMIT 记录并排除出结果等价分母；它们不会被计为通过。",
        ])
    lines.extend(["", "## 失败分类", "", "| 错误码 | 数量 |", "|---|---:|"])
    lines.extend(f"| {code} | {count} |" for code, count in report["errors"].items())
    if execution.get("status") == "NOT_RUN":
        lines.extend(["", "> 当前未执行真实 Doris 结果等价，静态 PASS 不能替代真实行集证据。", ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def _percentile(values: List[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)] / 1_000_000, 6)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"
