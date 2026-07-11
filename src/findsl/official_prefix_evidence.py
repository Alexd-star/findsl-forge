from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from .official.backend.doris import render_doris
from .official.backend.executor import execute_doris_query_digest
from .official.lowering import lower_official_ast
from .official.physical.catalog import default_physical_catalog
from .official.physical.planner import plan_physical
from .official.physical.statistics import default_physical_statistics
from .official.physical.strategies import default_physical_strategies
from .official.registry import default_official_registry
from .official.semantics import OfficialSemanticAnalyzer
from .official_slot import OfficialSlotCompiler, _resolve_indicator_meta, parse_official_slot
from .official_backend_evidence import _stable_projection_query


DEFAULT_PREFIX_EVIDENCE_SOURCES = (
    "indicator('', '', '5日均线', '', '', '', '') > 10",
    "indicator('', '', '5日均量线', '', '', '', '') > 1000",
)


def build_official_prefix_evidence(
    sources: Iterable[str] = DEFAULT_PREFIX_EVIDENCE_SOURCES,
    *,
    config,
    executor=execute_doris_query_digest,
):
    catalog = default_physical_catalog()
    statistics = default_physical_statistics(catalog)
    strategies = default_physical_strategies(catalog)
    analyzer = OfficialSemanticAnalyzer(_resolve_indicator_meta)
    compiler = OfficialSlotCompiler()
    results = []
    matched = 0
    errors = 0

    for source in sources:
        item = {"source": str(source)}
        try:
            typed = analyzer.analyze(parse_official_slot(source, mode="strict"))
            logical = lower_official_ast(typed, domain_registry=default_official_registry())
            default_plan = plan_physical(
                logical,
                catalog,
                statistics=statistics,
                strategies=strategies,
            )
            shadow_plan = plan_physical(
                logical,
                catalog,
                statistics=statistics,
                strategies=strategies,
                allow_shadow_strategies=True,
            )
            if default_plan.selected_strategy != "direct_column":
                raise ValueError("default planner selected an uncalibrated prefix strategy")
            if shadow_plan.selected_strategy == "direct_column":
                raise ValueError("no prefix shadow candidate was selected")
            legacy_sql = compiler.compile(source).sql
            shadow_sql = render_doris(shadow_plan.plan, catalog).sql
            legacy = executor(config, _stable_projection_query(legacy_sql))
            shadow = executor(config, _stable_projection_query(shadow_sql))
            equivalent = legacy.row_count == shadow.row_count and legacy.sha256 == shadow.sha256
            matched += int(equivalent)
            item.update(
                {
                    "status": "PASS" if equivalent else "MISMATCH",
                    "default_strategy": default_plan.selected_strategy,
                    "shadow_strategy": shadow_plan.selected_strategy,
                    "row_count": legacy.row_count,
                    "legacy_hash": legacy.sha256,
                    "shadow_hash": shadow.sha256,
                    "legacy_elapsed_ms": round(legacy.elapsed_ms, 6),
                    "shadow_elapsed_ms": round(shadow.elapsed_ms, 6),
                    "legacy_over_shadow_ratio": round(legacy.elapsed_ms / shadow.elapsed_ms, 6) if shadow.elapsed_ms else None,
                    "shadow_sql": shadow_sql,
                }
            )
        except Exception as exc:
            errors += 1
            item.update({"status": "ERROR", "error": str(exc)})
        results.append(item)

    passed = bool(results) and matched == len(results) and errors == 0
    return {
        "schema_version": 1,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "case_count": len(results),
        "matched": matched,
        "errors": errors,
        "git_head": _git_head(),
        "catalog_sha256": catalog.fingerprint,
        "results": results,
    }


def write_official_prefix_evidence(report, json_output, markdown_output):
    Path(json_output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 6B 官方前缀候选真实证据", "",
        f"- 门禁：`{report['status']}`",
        f"- 用例：`{report['case_count']}`",
        f"- 行集匹配：`{report['matched']}`",
        f"- 执行错误：`{report['errors']}`", "",
        "| DSL | 默认策略 | 影子策略 | 行数 | 旧后端 ms | 前缀 ms | 旧/前缀 | 状态 |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report["results"]:
        lines.append(
            f"| `{item['source']}` | {item.get('default_strategy', '-')} | {item.get('shadow_strategy', '-')} | "
            f"{item.get('row_count', '-')} | {item.get('legacy_elapsed_ms', '-')} | "
            f"{item.get('shadow_elapsed_ms', '-')} | {item.get('legacy_over_shadow_ratio', '-')} | {item['status']} |"
        )
    lines.extend([
        "",
        "> 只有结果哈希与性能均支持时，shadow 策略才可改为 active。比值小于 1 表示当前前缀 SQL 比旧技术表路径更慢。",
        "",
    ])
    Path(markdown_output).write_text("\n".join(lines), encoding="utf-8")


def _git_head():
    completed = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"
