from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQUIRED_REPORTS = {
    "quality": "final_quality_gates.json",
    "watermark": "official_doris_watermark.json",
    "correctness": "official_correctness_benchmark.json",
    "performance": "official_full_performance_matrix.json",
    "long_horizon": "official_long_horizon_matrix.json",
    "compile_latency": "official_compile_latency.json",
    "capability": "official_capability_matrix.json",
    "blind_extension": "blind_extension_evidence.json",
    "hero_query": "hero_query.json",
    "group_semantics": "group_entity_doris.json",
}


def build_final_submission_metadata(
    reports_dir: Path,
    *,
    expected_git_head: str | None = None,
) -> dict[str, Any]:
    reports_dir = reports_dir.resolve()
    expected = expected_git_head or _git_head()
    reports = {
        key: _load_json(reports_dir / filename)
        for key, filename in REQUIRED_REPORTS.items()
    }
    funnel = _load_json(reports_dir / "official_compiler_funnel.json")

    head_mismatches = {
        key: payload.get("git_head")
        for key, payload in reports.items()
        if payload.get("git_head") != expected
    }
    if head_mismatches:
        raise ValueError(
            f"evidence Git HEAD mismatch; expected {expected}: {head_mismatches}"
        )
    if funnel.get("git_head") != expected:
        raise ValueError(
            "official compiler funnel Git HEAD does not match the final release"
        )

    correctness = reports["correctness"]
    performance = reports["performance"]
    long_horizon = reports["long_horizon"]
    latency = reports["compile_latency"]
    capability = reports["capability"]
    blind = reports["blind_extension"]
    hero = reports["hero_query"]
    group = reports["group_semantics"]
    quality = reports["quality"]
    watermark = reports["watermark"]

    gates = {
        "quality_gates": bool(quality.get("all_passed")),
        "official_watermark": watermark.get("status") == "PASS",
        "sql_correctness": bool(correctness.get("target_met"))
        and correctness.get("matched") == correctness.get("eligible_total"),
        "query_execution": bool(performance.get("all_matched_reference"))
        and bool(performance.get("all_queries_under_10s")),
        "long_horizon_acceleration": bool(long_horizon.get("target_met"))
        and bool(long_horizon.get("all_complete_result_hashes_match"))
        and bool(long_horizon.get("all_optimized_p95_under_10s")),
        "compile_latency": bool(latency.get("target_met")),
        "twelve_function_families": bool(capability.get("gate", {}).get("passed")),
        "zero_core_code_extension": bool(blind.get("gate", {}).get("passed")),
        "hero_query": bool(hero.get("gate", {}).get("passed")),
        "group_semantics": bool(group.get("passed")),
    }
    failed = [name for name, passed in gates.items() if not passed]
    if failed:
        raise ValueError(f"final submission gate failure: {failed}")

    artifact_manifest = []
    for key, filename in REQUIRED_REPORTS.items():
        path = reports_dir / filename
        artifact_manifest.append(
            {
                "id": key,
                "file": filename,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    return {
        "schema_version": 1,
        "project": "FinDSL Forge",
        "competition_topic": "第五届中国研究生金融科技创新大赛赛题19",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "git_head": expected,
        "dataset_snapshot_id": correctness.get("dataset_snapshot_id"),
        "catalog_snapshot_id": correctness.get("catalog_snapshot_id"),
        "all_gates_passed": True,
        "gates": gates,
        "scorecard": {
            "correctness": {
                "matched": correctness["matched"],
                "eligible_total": correctness["eligible_total"],
                "accuracy": correctness["accuracy"],
                "wilson_95_lower": correctness["wilson_95"]["lower"],
                "all_12_function_families_covered": correctness[
                    "all_12_function_families_covered"
                ],
            },
            "execution": {
                "case_count": performance["case_count"],
                "passed": performance["passed"],
                "max_p95_ms": performance["max_p95_ms"],
                "all_queries_under_10s": performance["all_queries_under_10s"],
            },
            "long_horizon": {
                "workload_count": long_horizon["workload_count"],
                "minimum_speedup": long_horizon["minimum_speedup"],
                "median_speedup": long_horizon["median_speedup"],
                "hashes_match": long_horizon[
                    "all_complete_result_hashes_match"
                ],
            },
            "compile_latency": {
                "case_count": latency["case_count"],
                "sample_count": latency["sample_count"],
                "p50_ms": latency["p50_ms"],
                "p95_ms": latency["p95_ms"],
                "target_p95_ms": latency["target_p95_ms"],
            },
            "quality": {
                "pytest_passed": quality.get("pytest_passed"),
                "warning_count": quality.get("warning_count"),
                "command_count": len(quality.get("commands", [])),
            },
            "architecture_migration": {
                "legacy_strict_success": funnel["legacy_strict_success"],
                "legacy_to_new_migrated": funnel["legacy_to_new_migrated"],
                "migration_coverage": funnel["migration_coverage"],
                "new_backend_success": funnel["new_backend_success"],
            },
        },
        "artifacts": artifact_manifest,
    }


def write_final_submission_metadata(
    metadata: Mapping[str, Any],
    json_output: Path,
    markdown_output: Path,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_output.write_text(
        render_final_submission_markdown(metadata), encoding="utf-8"
    )


def render_final_submission_markdown(metadata: Mapping[str, Any]) -> str:
    score = metadata["scorecard"]
    correctness = score["correctness"]
    execution = score["execution"]
    long_horizon = score["long_horizon"]
    latency = score["compile_latency"]
    quality = score["quality"]
    return "\n".join(
        [
            "# FinDSL Forge 最终工程验收摘要",
            "",
            f"- Git HEAD：`{metadata['git_head']}`",
            f"- 数据快照：`{metadata['dataset_snapshot_id']}`",
            "- 最终门禁：`PASS`",
            "",
            "## 赛题核心指标",
            "",
            "| 指标 | 最终实测 | 结论 |",
            "|---|---:|---|",
            f"| SQL 正确率 | {correctness['matched']}/{correctness['eligible_total']}，Wilson 95% 下界 {correctness['wilson_95_lower'] * 100:.2f}% | PASS |",
            f"| 真实 Doris 执行 | {execution['passed']}/{execution['case_count']}，最大 P95 {execution['max_p95_ms']:.3f} ms | PASS |",
            f"| 长周期加速 | 最低 {long_horizon['minimum_speedup']:.3f}x，中位 {long_horizon['median_speedup']:.3f}x | PASS |",
            f"| 编译延迟 | P95 {latency['p95_ms']:.3f} ms / 目标 {latency['target_p95_ms']:.0f} ms | PASS |",
            f"| 自动化测试 | {quality['pytest_passed']} passed，warning {quality['warning_count']} | PASS |",
            "| 12 类函数全链路 | Parser 至 Doris SQL 全层覆盖 | PASS |",
            "| 配置式零核心改动扩展 | 核心源码树哈希保持一致 | PASS |",
            "",
            "## 工程交付",
            "",
            "项目源码、ANTLR4 文法、正式编译链、配置目录、Doris 部署资产、测试代码、独立 Reference SQL、性能工作负载和机器可读证据均已随交付包封装。所有评分证据由统一脚本在同一 Git HEAD 与同一 Doris 数据快照上生成，并由 SHA-256 清单校验。",
            "",
        ]
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required final evidence is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()
