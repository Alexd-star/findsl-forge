from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

from .context import CompileContext, default_compile_context
from .correctness import CorrectnessCase, OFFICIAL_FUNCTION_FAMILIES
from .pipeline import compile_official


def build_capability_matrix(
    cases: Iterable[CorrectnessCase],
    *,
    manifest_root: Path,
    context: CompileContext | None = None,
    compiler: Callable[..., Any] = compile_official,
) -> Dict[str, Any]:
    compile_context = context or default_compile_context()
    eligible = tuple(case for case in cases if case.score_eligible)
    records: Dict[str, Dict[str, Any]] = {
        family: {
            "function_family": family,
            "approved_reference_cases": 0,
            "mixed_composition_cases": 0,
            "plan_families": set(),
            "parser_pass": 0,
            "typed_ast_pass": 0,
            "logical_ir_pass": 0,
            "rewrite_contract_pass": 0,
            "physical_ir_pass": 0,
            "doris_sql_pass": 0,
            "failures": [],
        }
        for family in sorted(OFFICIAL_FUNCTION_FAMILIES)
    }
    compiled_cases = 0
    compile_failures = []
    for case in eligible:
        families = set(case.function_families) & OFFICIAL_FUNCTION_FAMILIES
        reference_exists = (Path(manifest_root) / case.reference_sql_path).is_file()
        for family in families:
            record = records[family]
            if reference_exists:
                record["approved_reference_cases"] += 1
            if len(families) > 1:
                record["mixed_composition_cases"] += 1
            record["plan_families"].add(case.plan_family)
        try:
            result = compiler(case.dsl, context=compile_context)
            compiled_cases += 1
        except Exception as exc:  # noqa: BLE001 - matrix keeps case-level diagnostics.
            failure = {
                "case_id": case.case_id,
                "error": f"{type(exc).__name__}: {exc}",
            }
            compile_failures.append(failure)
            for family in families:
                records[family]["failures"].append(failure)
            continue
        stage_flags = {
            "parser_pass": bool(result.frontend.get("ok")),
            "typed_ast_pass": bool(result.typed_ast.get("type")),
            "logical_ir_pass": bool(result.logical.get("validation_passed")),
            "rewrite_contract_pass": not result.optimized.get("diagnostics"),
            "physical_ir_pass": bool(result.physical.get("plan")),
            "doris_sql_pass": bool(
                result.backend.get("validation_passed")
                and result.backend.get("safety_passed")
            ),
        }
        for family in families:
            for key, passed in stage_flags.items():
                records[family][key] += int(passed)
    rows = []
    for family in sorted(records):
        raw = records[family]
        total = raw["approved_reference_cases"]
        layer_coverage = {
            key.removesuffix("_pass"): raw[key] == total and total > 0
            for key in (
                "parser_pass",
                "typed_ast_pass",
                "logical_ir_pass",
                "rewrite_contract_pass",
                "physical_ir_pass",
                "doris_sql_pass",
            )
        }
        rows.append(
            {
                "function_family": family,
                "approved_reference_cases": total,
                "mixed_composition_cases": raw["mixed_composition_cases"],
                "plan_families": sorted(raw["plan_families"]),
                "layer_coverage": layer_coverage,
                "all_layers_covered": all(layer_coverage.values()),
                "minimum_12_reference_cases": total >= 12,
                "failures": raw["failures"],
            }
        )
    gate = bool(
        len(rows) == 12
        and compiled_cases == len(eligible)
        and all(item["all_layers_covered"] for item in rows)
        and all(item["minimum_12_reference_cases"] for item in rows)
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "catalog_snapshot_id": compile_context.context_id,
        "eligible_case_count": len(eligible),
        "compiled_case_count": compiled_cases,
        "official_function_family_count": len(rows),
        "matrix": rows,
        "compile_failures": compile_failures,
        "gate": {
            "passed": gate,
            "all_12_families": len(rows) == 12,
            "all_cases_compile": compiled_cases == len(eligible),
            "all_layers_covered": all(item["all_layers_covered"] for item in rows),
            "every_family_has_12_oracles": all(
                item["minimum_12_reference_cases"] for item in rows
            ),
        },
    }


def write_capability_matrix(
    report: Mapping[str, Any],
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    columns = ("parser", "typed_ast", "logical_ir", "rewrite_contract", "physical_ir", "doris_sql")
    lines = [
        "# 十二类函数 Capability Matrix",
        "",
        f"- 正式样例：`{report['eligible_case_count']}`",
        f"- 编译成功：`{report['compiled_case_count']}`",
        f"- 十二类覆盖：`{report['gate']['all_12_families']}`",
        f"- 总门禁：`{'PASS' if report['gate']['passed'] else 'FAIL'}`",
        "",
        "| 函数族 | Reference | 混合组合 | Parser | Typed AST | Logical IR | Rule Contract | Physical IR | Doris SQL | 计划族 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["matrix"]:
        coverage = item["layer_coverage"]
        marks = ["PASS" if coverage[column] else "FAIL" for column in columns]
        lines.append(
            f"| `{item['function_family']}` | {item['approved_reference_cases']} | "
            f"{item['mixed_composition_cases']} | {' | '.join(marks)} | "
            f"{', '.join(item['plan_families'])} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
