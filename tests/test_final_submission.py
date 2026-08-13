from __future__ import annotations

import json
from pathlib import Path

import pytest

from findsl.final_submission import REQUIRED_REPORTS, build_final_submission_metadata


HEAD = "a" * 40


def test_final_submission_metadata_requires_every_gate_and_same_head(tmp_path: Path) -> None:
    payloads = _payloads()
    for key, filename in REQUIRED_REPORTS.items():
        (tmp_path / filename).write_text(
            json.dumps(payloads[key]), encoding="utf-8"
        )
    _write_funnel(tmp_path)

    result = build_final_submission_metadata(tmp_path, expected_git_head=HEAD)

    assert result["all_gates_passed"] is True
    assert result["scorecard"]["correctness"]["matched"] == 240
    assert result["scorecard"]["long_horizon"]["minimum_speedup"] == 11.9
    assert len(result["artifacts"]) == len(REQUIRED_REPORTS)


def test_final_submission_metadata_rejects_mixed_git_heads(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["blind_extension"]["git_head"] = "b" * 40
    for key, filename in REQUIRED_REPORTS.items():
        (tmp_path / filename).write_text(
            json.dumps(payloads[key]), encoding="utf-8"
        )
    _write_funnel(tmp_path)

    with pytest.raises(ValueError, match="Git HEAD mismatch"):
        build_final_submission_metadata(tmp_path, expected_git_head=HEAD)


def _payloads() -> dict:
    common = {"git_head": HEAD}
    return {
        "quality": {
            **common,
            "all_passed": True,
            "pytest_passed": 100,
            "warning_count": 0,
            "commands": [{"passed": True}],
        },
        "watermark": {**common, "status": "PASS"},
        "correctness": {
            **common,
            "target_met": True,
            "matched": 240,
            "eligible_total": 240,
            "accuracy": 1.0,
            "wilson_95": {"lower": 0.9842},
            "all_12_function_families_covered": True,
            "dataset_snapshot_id": "dataset-v1",
            "catalog_snapshot_id": "catalog-v1",
        },
        "performance": {
            **common,
            "all_matched_reference": True,
            "all_queries_under_10s": True,
            "case_count": 48,
            "passed": 48,
            "max_p95_ms": 2800.0,
        },
        "long_horizon": {
            **common,
            "target_met": True,
            "all_complete_result_hashes_match": True,
            "all_optimized_p95_under_10s": True,
            "workload_count": 5,
            "minimum_speedup": 11.9,
            "median_speedup": 13.6,
        },
        "compile_latency": {
            **common,
            "target_met": True,
            "case_count": 48,
            "sample_count": 1440,
            "p50_ms": 11.0,
            "p95_ms": 32.0,
            "target_p95_ms": 50.0,
        },
        "capability": {**common, "gate": {"passed": True}},
        "blind_extension": {**common, "gate": {"passed": True}},
        "hero_query": {**common, "gate": {"passed": True}},
        "group_semantics": {**common, "passed": True},
    }


def _write_funnel(root: Path) -> None:
    (root / "official_compiler_funnel.json").write_text(
        json.dumps(
            {
                "git_head": HEAD,
                "legacy_strict_success": 1097,
                "legacy_to_new_migrated": 1044,
                "migration_coverage": 0.951686,
                "new_backend_success": 1276,
            }
        ),
        encoding="utf-8",
    )
