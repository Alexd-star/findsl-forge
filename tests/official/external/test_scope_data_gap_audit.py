import json
from pathlib import Path

from findsl.official.external.source_registry import ExternalSourceRegistry
from scripts.audit_scope_data_gaps import build_audit, render_markdown


REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "submission_artifacts/evidence_snapshots"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_scope_data_gap_audit_covers_every_current_migration_gap() -> None:
    audit = build_audit(
        _load(EVIDENCE / "phase48_scope_semantic_policy_funnel.json"),
        _load(EVIDENCE / "phase48_true_remaining_scope_targets.json"),
        _load(REPO_ROOT / "configs/official/scope_gap_adjudications.json"),
        ExternalSourceRegistry.load(
            REPO_ROOT / "configs/official/external_source_registry.json"
        ),
        git_head="test-head",
    )

    assert audit["summary"]["migration_gap_rows"] == 53
    assert audit["summary"]["unresolved_targets"] == 57
    assert audit["summary"]["unresolved_occurrences"] == 76
    assert audit["summary"]["forced_fuzzy_mappings"] == 0
    assert len(audit["rows"]) == 53
    assert all(item["affected_excel_rows"] for item in audit["targets"])
    assert "确定性拒绝不是编译成功" in render_markdown(audit)
