from __future__ import annotations

import json
from pathlib import Path

import pytest

from findsl.official.financial_rules import (
    FinancialRuleCatalog,
    FinancialRuleCatalogError,
    validate_rule_release_transition,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "configs" / "official" / "financial_rules.json"


def _payload() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_active_financial_rule_release_is_versioned_and_fingerprinted() -> None:
    catalog = FinancialRuleCatalog.load(CATALOG_PATH, as_of_date="2026-08-13")

    assert catalog.schema_version == 2
    assert catalog.release.release_id == "financial-rules-2026-08-12"
    assert catalog.release.active_on("2026-08-13") is True
    assert len(catalog.fingerprint) == 64


def test_formal_context_rejects_non_active_or_future_release(tmp_path: Path) -> None:
    payload = _payload()
    payload["release"]["status"] = "shadow"
    shadow = _write(tmp_path / "shadow.json", payload)

    with pytest.raises(FinancialRuleCatalogError, match="not active"):
        FinancialRuleCatalog.load(shadow, as_of_date="2026-08-13")

    payload["release"]["status"] = "active"
    payload["release"]["effective_from"] = "2026-09-01"
    future = _write(tmp_path / "future.json", payload)
    with pytest.raises(FinancialRuleCatalogError, match="not active"):
        FinancialRuleCatalog.load(future, as_of_date="2026-08-13")


def test_release_transition_requires_rollback_chain_and_no_rule_downgrade(
    tmp_path: Path,
) -> None:
    baseline = FinancialRuleCatalog.load(CATALOG_PATH, as_of_date="2026-08-13")
    payload = _payload()
    payload["catalog_id"] = "financial-rule-catalog-v3"
    payload["release"].update(
        {
            "release_id": "financial-rules-candidate-001",
            "status": "shadow",
            "previous_catalog_id": baseline.catalog_id,
            "rollback_catalog_id": baseline.catalog_id,
        }
    )
    payload["rules"][0]["version"] = "2"
    candidate_path = _write(tmp_path / "candidate.json", payload)
    candidate = FinancialRuleCatalog.load(candidate_path, require_active=False)

    report = validate_rule_release_transition(baseline, candidate)

    assert report["passed"] is True
    assert report["changed_rule_ids"] == ["FR-ADJUSTMENT-001"]

    payload["rules"][0]["version"] = "0"
    invalid = FinancialRuleCatalog.load(
        _write(tmp_path / "invalid.json", payload), require_active=False
    )
    rejected = validate_rule_release_transition(baseline, invalid)
    assert rejected["passed"] is False
    assert "rule version cannot decrease" in " ".join(rejected["errors"])


def test_release_transition_requires_explicit_rule_retirement(tmp_path: Path) -> None:
    baseline = FinancialRuleCatalog.load(CATALOG_PATH, as_of_date="2026-08-13")
    payload = _payload()
    payload["catalog_id"] = "financial-rule-catalog-v3"
    payload["release"].update(
        {
            "release_id": "financial-rules-candidate-002",
            "status": "draft",
            "previous_catalog_id": baseline.catalog_id,
            "rollback_catalog_id": baseline.catalog_id,
        }
    )
    removed = payload["rules"].pop()["rule_id"]
    candidate = FinancialRuleCatalog.load(
        _write(tmp_path / "candidate.json", payload), require_active=False
    )

    report = validate_rule_release_transition(baseline, candidate)

    assert report["passed"] is False
    assert removed in " ".join(report["errors"])
