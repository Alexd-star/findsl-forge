from __future__ import annotations

import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .official.lowering import OfficialLoweringError, lower_official_ast
from .official.optimizer import DEFAULT_RULES, Optimizer
from .official.registry import default_official_registry
from .official.semantics import OfficialSemanticAnalyzer
from .official_ir_evidence import build_official_ir_evidence
from .official_slot import OfficialSlotError, _resolve_indicator_meta, parse_official_slot_with_diagnostics


def _percentile(values: List[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)] / 1_000_000, 6)


def _git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def build_official_domain_evidence(workbook: str, sample_size: int = 20) -> Dict[str, Any]:
    import pandas as pd

    baseline = build_official_ir_evidence(workbook, sample_size=sample_size)
    frame = pd.read_excel(workbook, sheet_name="训练语料", usecols=["slot_dsl"])
    analyzer = OfficialSemanticAnalyzer(_resolve_indicator_meta)
    registry = default_official_registry()
    optimizer = Optimizer(DEFAULT_RULES)
    domain_ok = optimized_validated = 0
    errors: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    domain_nodes: Counter[str] = Counter()
    latency: List[int] = []
    idempotence_checks = idempotence_mismatches = 0
    optimizer_diagnostics = 0
    samples = []
    for excel_row, source in enumerate(frame["slot_dsl"], start=2):
        source = str(source)
        try:
            parsed = parse_official_slot_with_diagnostics(source, mode="strict", frontend="antlr")
            typed = analyzer.analyze(parsed.ast)
            lowered = lower_official_ast(typed, strict=True, domain_registry=registry)
            domain_ok += 1
            optimized = optimizer.optimize(lowered.plan)
            if optimized.diagnostics:
                optimizer_diagnostics += 1
                errors["OPTIMIZER_VALIDATION_ERROR"] += 1
                continue
            optimized_validated += 1
            rules.update(event.rule_id for event in optimized.trace)
            for binding in lowered.domain_bindings:
                domain_nodes[binding.expression.to_dict().get("kind", type(binding.expression).__name__)] += 1
            latency.append(lowered.elapsed_ns + sum(event.elapsed_ns for event in optimized.trace))
            if idempotence_checks < 100:
                repeated = optimizer.optimize(optimized.plan)
                idempotence_mismatches += int(repeated.plan.node_id != optimized.plan.node_id or bool(repeated.trace))
                idempotence_checks += 1
        except OfficialSlotError as exc:
            errors[exc.code] += 1
        except OfficialLoweringError as exc:
            errors[exc.code] += 1
            if len(samples) < sample_size:
                samples.append({"excel_row": excel_row, "code": exc.code, "message": str(exc)})
    gate_passed = (
        baseline["strict_parse_ok"] >= 5792
        and baseline["strict_compile_ok"] >= 1097
        and baseline["lowering_ok"] >= 2034
        and optimized_validated == domain_ok
        and optimizer_diagnostics == 0
        and idempotence_mismatches == 0
    )
    return {
        "schema_version": 1,
        "git_head": _git_head(),
        "workbook": str(Path(workbook).resolve()),
        "input_sha256": baseline["input_sha256"],
        "row_count": baseline["row_count"],
        "strict_parse_ok": baseline["strict_parse_ok"],
        "strict_compile_ok": baseline["strict_compile_ok"],
        "phase3_lowering_ok": baseline["lowering_ok"],
        "registry_entries": len(registry),
        "domain_lowering_ok": domain_ok,
        "optimized_validated": optimized_validated,
        "binding_errors": dict(errors.most_common()),
        "domain_nodes": dict(domain_nodes.most_common()),
        "rule_hits": dict(rules.most_common()),
        "optimizer_diagnostics": optimizer_diagnostics,
        "idempotence_checks": idempotence_checks,
        "idempotence_mismatches": idempotence_mismatches,
        "latency_ms": {"p50": _percentile(latency, 0.50), "p95": _percentile(latency, 0.95)},
        "samples": samples,
        "gate": {"passed": gate_passed, "strict_parse_floor": 5792, "strict_compile_floor": 1097, "phase3_lowering_floor": 2034},
    }


def write_official_domain_evidence(report: Dict[str, Any], json_output: str, markdown_output: str) -> None:
    json_path, md_path = Path(json_output), Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 4 领域 IR 与规则优化器官方证据", "",
        f"- 门禁：`{'PASS' if report['gate']['passed'] else 'FAIL'}`",
        f"- 官方问句：`{report['row_count']}`",
        f"- 注册表条目：`{report['registry_entries']}`",
        f"- 领域 lowering 成功：`{report['domain_lowering_ok']}`",
        f"- 优化后验证通过：`{report['optimized_validated']}`",
        f"- 优化器诊断：`{report['optimizer_diagnostics']}`",
        f"- 幂等差异：`{report['idempotence_mismatches']}`",
        f"- bind + optimize P95：`{report['latency_ms']['p95']}` ms",
        f"- strict 编译基线：`{report['strict_compile_ok']}`", "",
        "> 领域绑定与规则命中不代表 Doris SQL 已执行，也不替代结果正确率证据。", "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
