from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .official.lowering import OfficialLoweringError, lower_official_ast
from .official.semantics import OfficialSemanticAnalyzer
from .official_slot import (
    OfficialSlotCompiler,
    OfficialSlotError,
    _resolve_indicator_meta,
    parse_official_slot_with_diagnostics,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: List[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)] / 1_000_000, 6)


def _git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _count_kinds(value: Any, counter: Counter) -> None:
    if isinstance(value, dict):
        if "kind" in value and isinstance(value["kind"], str):
            counter[value["kind"]] += 1
        for child in value.values():
            _count_kinds(child, counter)
    elif isinstance(value, list):
        for child in value:
            _count_kinds(child, counter)


def build_official_ir_evidence(workbook: str, sample_size: int = 20) -> Dict[str, Any]:
    import pandas as pd

    path = Path(workbook).resolve()
    frame = pd.read_excel(path, sheet_name="训练语料", usecols=["slot_dsl"])
    analyzer = OfficialSemanticAnalyzer(_resolve_indicator_meta)
    compiler = OfficialSlotCompiler(mode="strict")
    strict_parse_ok = typed_ok = lowering_ok = validated = strict_compile_ok = 0
    typed_errors: Counter[str] = Counter()
    lowering_errors: Counter[str] = Counter()
    node_kinds: Counter[str] = Counter()
    function_coverage: Counter[str] = Counter()
    elapsed: List[int] = []
    samples: List[Dict[str, Any]] = []
    deterministic_hash_mismatches = 0
    deterministic_checks = 0
    for excel_row, source in enumerate(frame["slot_dsl"], start=2):
        source = str(source)
        try:
            parsed = parse_official_slot_with_diagnostics(source, mode="strict", frontend="antlr")
            strict_parse_ok += 1
            typed = analyzer.analyze(parsed.ast)
            typed_ok += 1
            result = lower_official_ast(typed, strict=True)
            lowering_ok += 1
            validated += int(result.validation_passed)
            elapsed.append(result.elapsed_ns)
            _count_kinds(result.plan.to_dict(), node_kinds)
            function_coverage.update(result.required_functions)
            if deterministic_checks < 100:
                repeated = lower_official_ast(typed, strict=True)
                deterministic_hash_mismatches += int(result.plan.node_id != repeated.plan.node_id)
                deterministic_checks += 1
        except OfficialSlotError as exc:
            typed_errors[exc.code] += 1
        except OfficialLoweringError as exc:
            lowering_errors[exc.code] += 1
            if len(samples) < sample_size:
                samples.append({"excel_row": excel_row, "input_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(), "code": exc.code, "message": str(exc)})
        try:
            compiler.compile(source)
            strict_compile_ok += 1
        except OfficialSlotError:
            pass
    gate = {
        "passed": (
            strict_parse_ok >= 5792
            and strict_compile_ok >= 1097
            and validated == lowering_ok
            and deterministic_hash_mismatches == 0
        ),
        "strict_parse_floor": 5792,
        "strict_compile_floor": 1097,
    }
    return {
        "schema_version": 1,
        "workbook": str(path),
        "input_sha256": _sha256(path),
        "git_head": _git_head(),
        "row_count": int(len(frame)),
        "strict_parse_ok": strict_parse_ok,
        "typed_ok": typed_ok,
        "lowering_ok": lowering_ok,
        "validated_plan_count": validated,
        "strict_compile_ok": strict_compile_ok,
        "typed_errors": dict(sorted(typed_errors.items())),
        "lowering_errors": dict(sorted(lowering_errors.items())),
        "node_kinds": dict(node_kinds.most_common()),
        "function_coverage": dict(function_coverage.most_common()),
        "deterministic_hash_checks": deterministic_checks,
        "deterministic_hash_mismatches": deterministic_hash_mismatches,
        "latency_ms": {"p50": _percentile(elapsed, 0.50), "p95": _percentile(elapsed, 0.95)},
        "samples": samples,
        "gate": gate,
    }


def write_official_ir_evidence(report: Dict[str, Any], json_output: str, markdown_output: str) -> None:
    json_path, markdown_path = Path(json_output), Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 3 Typed AST 与 Logical IR 官方证据",
        "",
        f"- 门禁：`{'PASS' if report['gate']['passed'] else 'FAIL'}`",
        f"- 官方问句：`{report['row_count']}`",
        f"- strict 解析成功：`{report['strict_parse_ok']}`",
        f"- Typed AST 成功：`{report['typed_ok']}`",
        f"- Logical IR 成功：`{report['lowering_ok']}`",
        f"- IR 验证通过：`{report['validated_plan_count']}`",
        f"- 既有 strict 编译成功：`{report['strict_compile_ok']}`",
        f"- Lowering P95：`{report['latency_ms']['p95']}` ms",
        f"- 确定性哈希差异：`{report['deterministic_hash_mismatches']}`",
        f"- 输入 SHA-256：`{report['input_sha256']}`",
        f"- Git HEAD：`{report['git_head']}`",
        "",
        "> IR 成功率只表示当前结构可被严格降低和验证，不代表 SQL 行集正确率或数据域完整率。",
        "",
    ]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
