from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, List

from .official.frontend.shadow import compare_frontends


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: List[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index] / 1_000_000, 6)


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def build_frontend_evidence(workbook: str, sample_size: int = 20) -> Dict[str, Any]:
    import pandas as pd

    path = Path(workbook).resolve()
    frame = pd.read_excel(path, sheet_name="训练语料", usecols=["slot_dsl"])
    modes: Dict[str, Dict[str, Any]] = {}
    for mode in ("strict", "recovery"):
        classifications: Counter[str] = Counter()
        timings = {"handwritten": [], "antlr": []}
        samples = defaultdict(list)
        handwritten_parse_ok = 0
        antlr_parse_ok = 0
        for row_index, value in enumerate(frame["slot_dsl"], start=2):
            comparison = compare_frontends(str(value), mode=mode)
            classifications[comparison.classification] += 1
            timings["handwritten"].append(comparison.handwritten_elapsed_ns)
            timings["antlr"].append(comparison.antlr_elapsed_ns)
            if not comparison.handwritten_diagnostics:
                handwritten_parse_ok += 1
            if not comparison.antlr_diagnostics:
                antlr_parse_ok += 1
            bucket = samples[comparison.classification]
            if comparison.classification != "MATCH" and len(bucket) < sample_size:
                item = comparison.to_dict()
                item["excel_row"] = row_index
                bucket.append(item)
        modes[mode] = {
            "classifications": dict(sorted(classifications.items())),
            "handwritten_parse_ok": handwritten_parse_ok,
            "antlr_parse_ok": antlr_parse_ok,
            "latency_ms": {
                name: {"p50": _percentile(values, 0.50), "p95": _percentile(values, 0.95)}
                for name, values in timings.items()
            },
            "samples": dict(samples),
        }
    blocking_classes = ("AST_MISMATCH", "ANTLR_REJECTED", "HANDWRITTEN_REJECTED")
    blocking_divergences = sum(
        modes[mode]["classifications"].get(name, 0)
        for mode in ("strict", "recovery")
        for name in blocking_classes
    )
    diagnostic_only = sum(
        modes[mode]["classifications"].get("ERROR_MISMATCH", 0)
        for mode in ("strict", "recovery")
    )
    recovery_all_match = modes["recovery"]["classifications"] == {"MATCH": len(frame)}
    return {
        "schema_version": 1,
        "workbook": str(path),
        "input_sha256": _file_sha256(path),
        "sheet": "训练语料",
        "row_count": int(len(frame)),
        "antlr_runtime": version("antlr4-python3-runtime"),
        "git_head": _git_head(),
        "migration_gate": {
            "passed": blocking_divergences == 0 and recovery_all_match,
            "blocking_divergences": blocking_divergences,
            "diagnostic_only_divergences": diagnostic_only,
            "policy": "AST differences and one-sided acceptance block migration; dual rejection with different first-error stages is audited but non-blocking.",
        },
        "strict": modes["strict"],
        "recovery": modes["recovery"],
    }


def write_frontend_evidence(report: Dict[str, Any], json_output: str, markdown_output: str) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# ANTLR 影子前端官方语料差分证据",
        "",
        f"- 官方语料：`{report['row_count']}` 条",
        f"- 输入 SHA-256：`{report['input_sha256']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- ANTLR runtime：`{report['antlr_runtime']}`",
        f"- 迁移门禁：`{'PASS' if report['migration_gate']['passed'] else 'FAIL'}`",
        f"- 阻断差异：`{report['migration_gate']['blocking_divergences']}`",
        f"- 仅诊断阶段差异：`{report['migration_gate']['diagnostic_only_divergences']}`",
    ]
    for mode in ("strict", "recovery"):
        value = report[mode]
        lines.extend(
            [
                "",
                f"## {mode} 模式",
                "",
                f"- 手写前端解析成功：`{value['handwritten_parse_ok']}`",
                f"- ANTLR 前端解析成功：`{value['antlr_parse_ok']}`",
                f"- 手写前端 P95：`{value['latency_ms']['handwritten']['p95']}` ms",
                f"- ANTLR 前端 P95：`{value['latency_ms']['antlr']['p95']}` ms",
                "",
                "| 差分分类 | 数量 |",
                "|---|---:|",
            ]
        )
        lines.extend(f"| {name} | {count} |" for name, count in value["classifications"].items())
    lines.extend(
        [
            "",
            "> 本报告只证明语法前端兼容性，不证明金融语义、SQL 行集正确率或 Doris 性能。",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
