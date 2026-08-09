from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from findsl.official.backend.diff import hash_result_rows
from findsl.official.backend.executor import DorisExecutionConfig, DorisExecutionResult
from findsl.official.context import CompileContext
from findsl.official.correctness import (
    CorrectnessCase,
    CorrectnessContractError,
    load_correctness_manifest,
    run_correctness_benchmark,
    validate_correctness_manifest,
    wilson_interval,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_manifest_rejects_eligible_case_without_approval(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(_raw_case(review_status="pending")), encoding="utf-8")

    cases = load_correctness_manifest(manifest)
    audit = validate_correctness_manifest(cases, root=tmp_path)

    assert audit["passed"] is False
    assert "eligible case must be approved" in audit["errors"][0]


def test_approved_reference_must_exist(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(_raw_case()), encoding="utf-8")

    audit = validate_correctness_manifest(load_correctness_manifest(manifest), root=tmp_path)

    assert audit["passed"] is False
    assert "approved reference SQL is missing" in audit["errors"][0]


def test_runner_compares_complete_unordered_row_sets(tmp_path: Path) -> None:
    (tmp_path / "ref1.sql").write_text("reference1", encoding="utf-8")
    (tmp_path / "ref2.sql").write_text("reference2", encoding="utf-8")
    context = CompileContext.load(REPO_ROOT)
    cases = (
        _case("C1", "dsl1", "ref1.sql", context.snapshot.policy_id),
        _case("C2", "dsl2", "ref2.sql", context.snapshot.policy_id),
    )

    def compiler(dsl, *, context):
        return SimpleNamespace(backend={"sql": "generated" + dsl[-1]}, elapsed_ms=1.25)

    rows = {
        "generated1": (("1",), ("2",)),
        "reference1": (("2",), ("1",)),
        "generated2": (("3",),),
        "reference2": (("4",),),
    }

    def executor(config, sql):
        values = rows[sql]
        return DorisExecutionResult(
            values,
            2.0,
            hash_result_rows(values, ordered=True),
            hash_result_rows(values, ordered=False),
        )

    report = run_correctness_benchmark(
        cases,
        manifest_root=tmp_path,
        doris=DorisExecutionConfig("127.0.0.1", 9030, "root", "", "newzl"),
        context=context,
        compiler=compiler,
        executor=executor,
    )

    assert report["eligible_total"] == 2
    assert report["matched"] == 1
    assert report["accuracy"] == 0.5
    assert report["target_met"] is False
    assert report["groups"]["function_family"]["indicator"]["matched"] == 1


def test_wilson_interval_is_bounded_and_not_point_estimate() -> None:
    lower, upper = wilson_interval(95, 100)

    assert 0 < lower < 0.95 < upper < 1
    assert wilson_interval(0, 0) == (None, None)


def test_manifest_rejects_duplicate_ids(tmp_path: Path) -> None:
    raw = json.dumps(_raw_case())
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(raw + "\n" + raw, encoding="utf-8")

    with pytest.raises(CorrectnessContractError, match="duplicate"):
        load_correctness_manifest(manifest)


def _case(case_id: str, dsl: str, reference: str, policy_id: str) -> CorrectnessCase:
    return CorrectnessCase(
        case_id,
        dsl,
        ("indicator",),
        "ordinary_scan",
        "eligible",
        "official fields available",
        policy_id,
        "snapshot-v1",
        True,
        reference,
        "approved",
        "independent-reviewer",
        False,
    )


def _raw_case(review_status: str = "approved") -> dict:
    return {
        "case_id": "CORR-001",
        "dsl": "indicator('', '', '成交量', '今日', '', '', '') > 1",
        "function_families": ["indicator"],
        "plan_family": "ordinary_scan",
        "eligibility": "eligible",
        "eligibility_reason": "official fields available",
        "policy_id": "official-semantic-policy-v1",
        "dataset_snapshot_id": "snapshot-v1",
        "expected_non_empty": True,
        "reference_sql_path": "reference_sql/CORR-001.sql",
        "review_status": review_status,
        "reviewer": "reviewer" if review_status == "approved" else "",
        "ordered": False,
    }
