from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Dict, Iterable, List

from .official.backend.doris import render_doris
from .official.lowering import lower_official_ast
from .official.physical.catalog import default_physical_catalog
from .official.physical.planner import plan_physical
from .official.registry import default_official_registry
from .official.semantics import OfficialSemanticAnalyzer
from .official_slot import _resolve_indicator_meta, parse_official_slot_with_diagnostics


def audit_official_backend_sources(sources: Iterable[str], sample_size: int = 20) -> Dict[str, Any]:
    analyzer = OfficialSemanticAnalyzer(_resolve_indicator_meta)
    registry = default_official_registry()
    catalog = default_physical_catalog()
    typed_ok = logical_ok = physical_ok = sqlglot_ok = safety_ok = 0
    errors: Counter[str] = Counter()
    resources: Counter[str] = Counter()
    latencies: List[int] = []
    samples = []
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
            physical = plan_physical(logical, catalog)
            physical_ok += 1
            resources[physical.selected_resource] += 1
            stage = "sqlglot"
            rendered = render_doris(physical.plan, catalog)
            sqlglot_ok += int(rendered.round_trip_stable)
            safety_ok += int(rendered.validation.passed)
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
        "real_doris_execution": {
            "status": "NOT_RUN",
            "reason": "Static backend audit does not imply execution or result equivalence on a live Doris cluster.",
        },
    }


def build_official_backend_evidence(workbook: str, sample_size: int = 20) -> Dict[str, Any]:
    import pandas as pd

    path = Path(workbook).resolve()
    frame = pd.read_excel(path, sheet_name="训练语料", usecols=["slot_dsl"])
    report = audit_official_backend_sources(frame["slot_dsl"], sample_size=sample_size)
    report.update(
        {
            "workbook": str(path),
            "input_sha256": _file_sha256(path),
            "git_head": _git_head(),
        }
    )
    return report


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
        "## 失败分类", "", "| 错误码 | 数量 |", "|---|---:|",
    ]
    lines.extend(f"| {code} | {count} |" for code, count in report["errors"].items())
    lines.extend([
        "", "> 本报告是静态编译后端证据，不等同于真实 Doris 执行、结果等价或性能证据。", "",
    ])
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
