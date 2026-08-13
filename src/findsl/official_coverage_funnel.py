from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from .official.pipeline import OfficialPipelineError, compile_official
from .official_slot import OfficialSlotCompiler


STAGES = ("frontend", "typed", "logical", "optimizer", "physical", "backend")


def build_official_coverage_funnel(sources: Iterable[str]) -> Dict[str, Any]:
    source_list = [str(item) for item in sources]
    legacy = OfficialSlotCompiler(mode="strict")
    stage_success: Counter[str] = Counter()
    terminal_errors: Counter[str] = Counter()
    migration_gaps: Counter[str] = Counter()
    family_stats: Dict[str, Counter[str]] = defaultdict(Counter)
    rows: List[Dict[str, Any]] = []
    legacy_success_count = new_success_count = migrated = 0

    for excel_row, source in enumerate(source_list, start=2):
        legacy_ok, legacy_code = _legacy_outcome(legacy, source)
        legacy_success_count += int(legacy_ok)
        try:
            result = compile_official(source)
            payload = result.to_dict()
            new_ok = True
            terminal_stage = "backend"
            terminal_code = "PASS"
            partial = payload
            for stage in STAGES:
                stage_success[stage] += 1
        except OfficialPipelineError as exc:
            new_ok = False
            terminal_stage = exc.stage
            terminal_code = exc.code
            partial = exc.partial
            terminal_errors[terminal_code] += 1
            _count_completed_stages(stage_success, partial)

        new_success_count += int(new_ok)
        if legacy_ok and new_ok:
            migrated += 1
        elif legacy_ok:
            migration_gaps[terminal_code] += 1

        functions = sorted(_function_names(partial.get("frontend", {}).get("ast")))
        for function in functions:
            stats = family_stats[function]
            stats["rows"] += 1
            stats["legacy_strict_success"] += int(legacy_ok)
            stats["new_backend_success"] += int(new_ok)
        physical = partial.get("physical", {})
        rows.append(
            {
                "excel_row": excel_row,
                "source": source,
                "functions": functions,
                "legacy_strict_success": legacy_ok,
                "legacy_code": legacy_code,
                "new_backend_success": new_ok,
                "terminal_stage": terminal_stage,
                "terminal_code": terminal_code,
                "selected_resource": physical.get("selected_resource"),
                "selected_strategy": physical.get("selected_strategy"),
            }
        )

    return {
        "schema_version": 1,
        "row_count": len(source_list),
        "source_sha256": hashlib.sha256("\n".join(source_list).encode("utf-8")).hexdigest(),
        "git_head": _git_head(),
        "legacy_strict_success": legacy_success_count,
        "new_backend_success": new_success_count,
        "legacy_to_new_migrated": migrated,
        "migration_coverage": round(migrated / legacy_success_count, 6) if legacy_success_count else 0.0,
        "stage_success": {stage: stage_success[stage] for stage in STAGES},
        "terminal_errors": dict(terminal_errors.most_common()),
        "migration_gaps": [
            {"code": code, "count": count}
            for code, count in migration_gaps.most_common()
        ],
        "function_families": {
            name: {
                "rows": stats["rows"],
                "legacy_strict_success": stats["legacy_strict_success"],
                "new_backend_success": stats["new_backend_success"],
            }
            for name, stats in sorted(family_stats.items())
        },
        "rows": rows,
    }


def build_official_workbook_coverage_funnel(workbook: str) -> Dict[str, Any]:
    import pandas as pd

    path = Path(workbook).resolve()
    frame = pd.read_excel(path, sheet_name="训练语料", usecols=["slot_dsl"])
    report = build_official_coverage_funnel(frame["slot_dsl"])
    # Evidence packages retain the official file identity without leaking the
    # workstation-specific extraction path.
    report["workbook"] = path.name
    report["input_sha256"] = _file_sha256(path)
    return report


def write_official_coverage_funnel(report: Dict[str, Any], json_output: str, report_output: str) -> None:
    json_path = Path(json_output)
    markdown_path = Path(report_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_official_coverage_funnel_markdown(report), encoding="utf-8")


def render_official_coverage_funnel_markdown(report: Dict[str, Any]) -> str:
    total = report["row_count"]
    legacy = report["legacy_strict_success"]
    migrated = report["legacy_to_new_migrated"]
    lines = [
        "# 官方编译器迁移覆盖漏斗",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 官方语料：`{total}`",
        f"- 旧严格后端成功集：`{legacy}`",
        f"- 新后端成功：`{report['new_backend_success']}`",
        f"- 旧严格后端成功集已迁移：`{migrated}/{legacy}`（`{report['migration_coverage'] * 100:.2f}%`）",
        "",
        "## 阶段漏斗",
        "",
        "| 阶段 | 成功数 | 占总语料 |",
        "|---|---:|---:|",
    ]
    for stage in STAGES:
        count = report["stage_success"][stage]
        ratio = count / total * 100 if total else 0.0
        lines.append(f"| {stage} | {count} | {ratio:.2f}% |")
    lines.extend(["", "## 迁移缺口优先级", "", "| 错误码 | 旧后端成功但新后端失败 |", "|---|---:|"])
    if report["migration_gaps"]:
        for item in report["migration_gaps"]:
            lines.append(f"| `{item['code']}` | {item['count']} |")
    else:
        lines.append("| `<none>` | 0 |")
    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            f"不得把 {total} 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。",
            "",
            "下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。",
        ]
    )
    return "\n".join(lines) + "\n"


def _legacy_outcome(compiler: OfficialSlotCompiler, source: str):
    try:
        compiler.compile(source)
        return True, "PASS"
    except Exception as exc:
        return False, str(getattr(exc, "code", type(exc).__name__))


def _count_completed_stages(counter: Counter[str], partial: Dict[str, Any]) -> None:
    mapping = {
        "frontend": "frontend",
        "typed": "typed_ast",
        "logical": "logical",
        "optimizer": "optimized",
        "physical": "physical",
    }
    for stage, key in mapping.items():
        if key in partial and (stage != "frontend" or partial[key].get("ok")):
            counter[stage] += 1


def _function_names(node: Any) -> Set[str]:
    if not isinstance(node, dict):
        return set()
    names: Set[str] = set()
    if node.get("type") == "FunctionCall" and node.get("name"):
        names.add(str(node["name"]))
    for value in node.values():
        if isinstance(value, dict):
            names.update(_function_names(value))
        elif isinstance(value, list):
            for item in value:
                names.update(_function_names(item))
    return names


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "<unknown>"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
