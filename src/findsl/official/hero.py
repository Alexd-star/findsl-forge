from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from .backend.executor import (
    DorisExecutionConfig,
    execute_doris_explain,
    execute_doris_query,
)
from .context import default_compile_context
from .pipeline import compile_official


class HeroQueryError(ValueError):
    pass


def run_hero_query(
    spec_path: Path,
    *,
    doris: DorisExecutionConfig | None = None,
    compiler: Callable[..., Any] = compile_official,
    executor: Callable[..., Any] = execute_doris_query,
    explainer: Callable[..., Any] = execute_doris_explain,
) -> Dict[str, Any]:
    spec = _load_spec(spec_path)
    if compiler is compile_official:
        context = default_compile_context()
        compiler(spec["dsl"], context=context)
        compiled = compiler(spec["dsl"], context=context)
        compile_warmups = 1
    else:
        compiled = compiler(spec["dsl"])
        compile_warmups = 0
    features = compiled.explain["query_features"]
    feature_checks = {
        name: bool(features.get(name)) for name in spec["required_features"]
    }
    temporal_check = set(spec["required_temporal_modes"]).issubset(
        features["temporal_modes"]
    )
    boolean_check = set(spec["required_boolean_operators"]).issubset(
        features["boolean_operators"]
    )
    reference_path = (spec_path.parent / spec["reference_sql_path"]).resolve()
    compile_gate = bool(
        all(feature_checks.values())
        and temporal_check
        and boolean_check
        and compiled.backend["validation_passed"]
        and compiled.backend["safety_passed"]
        and reference_path.is_file()
    )
    execution: Dict[str, Any] = {
        "status": "NOT_RUN",
        "reason": "Doris execution was not requested",
        "result_equivalent": None,
        "under_10_seconds": None,
    }
    if doris is not None:
        generated = executor(doris, compiled.backend["sql"])
        reference = executor(doris, reference_path.read_text(encoding="utf-8"))
        explain = explainer(doris, compiled.backend["sql"])
        equivalent = bool(
            len(generated.rows) == len(reference.rows)
            and generated.unordered_hash == reference.unordered_hash
        )
        execution = {
            "status": "PASS" if equivalent and generated.elapsed_ms <= 10_000 else "FAIL",
            "generated_row_count": len(generated.rows),
            "reference_row_count": len(reference.rows),
            "generated_hash": generated.unordered_hash,
            "reference_hash": reference.unordered_hash,
            "result_equivalent": equivalent,
            "generated_elapsed_ms": round(generated.elapsed_ms, 6),
            "reference_elapsed_ms": round(reference.elapsed_ms, 6),
            "under_10_seconds": generated.elapsed_ms <= 10_000,
            "doris_explain_elapsed_ms": round(explain.elapsed_ms, 6),
            "doris_explain": explain.text,
        }
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(spec_path.parents[2]),
        "hero_id": spec["hero_id"],
        "title": spec["title"],
        "dsl": spec["dsl"],
        "semantic_note": spec["semantic_note"],
        "feature_checks": feature_checks,
        "temporal_modes_passed": temporal_check,
        "boolean_operators_passed": boolean_check,
        "query_features": features,
        "compile_elapsed_ms": compiled.elapsed_ms,
        "compile_warmups": compile_warmups,
        "compile_latency_scope": "warmed_service_request",
        "selected_route": compiled.explain["adaptive_route"]["selected_route"],
        "selected_strategy": compiled.physical["selected_strategy"],
        "adaptive_route": compiled.explain["adaptive_route"],
        "catalog_snapshot_id": compiled.compile_context["context_id"],
        "generated_sql": compiled.backend["sql"],
        "reference_sql_path": str(reference_path),
        "execution": execution,
        "gate": {
            "compile_and_feature_gate": compile_gate,
            "doris_runtime_gate": execution["status"] == "PASS" if doris else None,
            "passed": compile_gate and (execution["status"] == "PASS" if doris else True),
        },
    }


def write_hero_report(
    report: Mapping[str, Any], json_path: Path, markdown_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    execution = report["execution"]
    lines = [
        "# Hero Query 端到端证据",
        "",
        f"- 查询：`{report['hero_id']}`",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 编译耗时：`{report['compile_elapsed_ms']:.4f} ms`",
        f"- 编译口径：`{report['compile_latency_scope']}`（warmups={report['compile_warmups']}）",
        f"- 选择路由：`{report['selected_route']}`",
        f"- 选择策略：`{report['selected_strategy']}`",
        f"- 选择候选：`{report['adaptive_route']['selected_candidate_id']}`",
        f"- 选择原因：`{report['adaptive_route']['selection_reason_code']}`",
        f"- 回退顺序：`{' -> '.join(report['adaptive_route']['fallback_chain']) or '<none>'}`",
        f"- 编译/特征门禁：`{'PASS' if report['gate']['compile_and_feature_gate'] else 'FAIL'}`",
        f"- Doris 运行门禁：`{execution['status']}`",
        "",
        "## DSL",
        "",
        f"```text\n{report['dsl']}\n```",
        "",
        "## 语义说明",
        "",
        report["semantic_note"],
        "",
        "## 复杂能力核验",
        "",
        "| 能力 | 通过 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{name}` | {passed} |"
        for name, passed in report["feature_checks"].items()
    )
    lines.extend(
        [
            f"| `CONS + EXIST` | {report['temporal_modes_passed']} |",
            f"| `and + then` | {report['boolean_operators_passed']} |",
        ]
    )
    if execution["status"] != "NOT_RUN":
        lines.extend(
            [
                "",
                "## Doris 实测",
                "",
                f"- 完整结果集一致：`{execution['result_equivalent']}`",
                f"- Generated rows / Reference rows：`{execution['generated_row_count']} / {execution['reference_row_count']}`",
                f"- Generated latency：`{execution['generated_elapsed_ms']:.3f} ms`",
                f"- 执行时间不超过 10 秒：`{execution['under_10_seconds']}`",
            ]
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_spec(path: Path) -> Dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version",
        "hero_id",
        "title",
        "dsl",
        "required_features",
        "required_temporal_modes",
        "required_boolean_operators",
        "reference_sql_path",
        "semantic_note",
    }
    if not isinstance(raw, dict) or set(raw) != expected or raw["schema_version"] != 1:
        raise HeroQueryError("invalid hero query specification")
    return raw


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"
