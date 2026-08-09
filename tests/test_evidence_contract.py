from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from findsl.evidence_contract import (
    EvidenceContract,
    EvidenceContractError,
    assert_evidence_contract,
    audit_evidence_metadata,
)


CONTRACT_PATH = Path("configs/official/evidence_contract.json")
HEAD = "7ace3ee0932e70a963eb948be03568cad68400b9"


def _metadata() -> dict:
    return {
        "git": {
            "head_at_report_generation": HEAD,
            "head_at_export": HEAD[:7],
        },
        "readiness": {"compile_p95_latency_ms": 1.5},
        "official_real_data": {
            "slot_coverage": {
                "git_head": HEAD,
                "row_count": 5799,
                "parse_ok": 5799,
                "compile_ok": 1830,
            },
            "doris": {
                "git_head": HEAD,
                "snapshot_fingerprint": "d" * 64,
            },
            "performance_matrix": {
                "git_head": HEAD,
                "all_queries_under_10s": True,
            },
            "long_horizon": {
                "git_head": HEAD,
                "target_met": True,
            },
        },
        "official_migration": {
            "git_head": HEAD,
            "row_count": 5799,
            "input_sha256": "a" * 64,
            "legacy_strict_success": 1097,
            "legacy_to_new_migrated": 1044,
            "new_backend_success": 1076,
        },
        "formal_correctness": {
            "git_head": HEAD,
            "eligible_total": 127,
            "matched": 127,
        },
        "doris_cluster": {"git_head": HEAD},
    }


def test_repository_evidence_contract_is_valid_and_auditable() -> None:
    contract = EvidenceContract.load(CONTRACT_PATH)

    audit = assert_evidence_contract(_metadata(), contract, expected_git_head=HEAD)

    assert audit["passed"] is True
    assert audit["metrics"]["legacy_migration_coverage"]["metric_type"] == "migration"
    assert audit["metrics"]["legacy_migration_coverage"]["ratio"] == pytest.approx(
        1044 / 1097
    )
    assert audit["metrics"]["sql_correctness"]["ratio"] == 1.0


def test_evidence_contract_rejects_mixed_current_heads() -> None:
    metadata = _metadata()
    metadata["official_real_data"]["long_horizon"]["git_head"] = "deadbee"

    audit = audit_evidence_metadata(
        metadata,
        EvidenceContract.load(CONTRACT_PATH),
        expected_git_head=HEAD,
    )

    assert audit["passed"] is False
    assert any("mixed Git HEAD" in item for item in audit["errors"])


def test_evidence_contract_rejects_missing_data_snapshot() -> None:
    metadata = _metadata()
    metadata["official_real_data"]["doris"]["snapshot_fingerprint"] = None

    with pytest.raises(EvidenceContractError, match="official_doris_snapshot"):
        assert_evidence_contract(metadata, EvidenceContract.load(CONTRACT_PATH))


def test_evidence_contract_cannot_label_migration_as_correctness(tmp_path: Path) -> None:
    raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    broken = copy.deepcopy(raw)
    for metric in broken["metrics"]:
        if metric["metric_id"] == "legacy_migration_coverage":
            metric["metric_type"] = "correctness"
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")

    audit = audit_evidence_metadata(_metadata(), EvidenceContract.load(path))

    assert audit["passed"] is False
    assert "legacy migration coverage must not be typed as SQL correctness" in audit["errors"]


def test_evidence_contract_rejects_ambiguous_metric_shape() -> None:
    raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    raw["metrics"][0]["value_path"] = "readiness.warning_count"

    with pytest.raises(EvidenceContractError, match="either value_path"):
        EvidenceContract.from_dict(raw)
