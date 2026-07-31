import pytest

from findsl.official.external.policy import (
    ScopeSemanticPolicyCatalog,
    ScopeSemanticPolicyError,
)
from findsl.official.external.runtime import (
    ExternalScopeRuntimeCatalog,
    ExternalScopeRuntimeError,
)


def _entry(**overrides):
    entry = {
        "policy_id": "technology-v1",
        "aliases": ["科技"],
        "resolution_kind": "exact_scope",
        "scope_name": "科技",
        "minimum_member_count": 100,
        "maximum_member_count": 2000,
        "semantic_basis": "business_policy",
        "confidence": "medium",
        "risk_level": "medium",
        "review_status": "approved",
        "effective_from": "2026-07-15",
        "rationale": "fixture policy",
        "rationale_urls": ["https://example.test/policy"],
        "data_boundary": "fixture boundary",
        "target": {"source_snapshot_id": "source-v1", "scope_code": "TMT"},
    }
    entry.update(overrides)
    return entry


def _catalog(*entries, risks=("low", "medium")):
    return ScopeSemanticPolicyCatalog.from_dict(
        {
            "schema_version": 1,
            "policy_set_id": "fixture-v1",
            "profile": "competition",
            "allowed_risk_levels": list(risks),
            "entries": list(entries),
        }
    )


def _runtime_entry(scope_code="TMT"):
    return {
        "scope_type": "concept",
        "scope_code": scope_code,
        "scope_name": "TMT",
        "alias": "科技",
        "normalized_alias": "科技",
        "source": "curated-scope-alias",
        "as_of_date": "2026-08-01",
        "snapshot_id": "curated-v1",
    }


def test_policy_catalog_resolves_reviewed_alias_and_preserves_audit_metadata():
    catalog = _catalog(_entry())

    policy = catalog.resolve("科技")

    assert policy.scope_code == "TMT"
    assert policy.semantic_basis == "business_policy"
    assert policy.to_audit_dict()["data_boundary"] == "fixture boundary"


def test_policy_catalog_rejects_alias_conflict_and_disallowed_risk():
    with pytest.raises(ScopeSemanticPolicyError, match="conflicting"):
        _catalog(_entry(), _entry(policy_id="technology-v2"))

    with pytest.raises(ScopeSemanticPolicyError, match="rejects policy risk"):
        _catalog(_entry(risk_level="high"))


def test_runtime_rejects_policy_target_drift_instead_of_selecting_another_scope():
    policies = _catalog(_entry())
    runtime = ExternalScopeRuntimeCatalog(
        (_runtime_entry("OTHER"),),
        membership_resource_id="external_scope_membership",
        semantic_policies=policies,
    )

    with pytest.raises(ExternalScopeRuntimeError, match="target is absent"):
        runtime.resolve("科技")


def test_runtime_attaches_semantic_policy_provenance_to_resolution():
    policies = _catalog(_entry())
    runtime = ExternalScopeRuntimeCatalog(
        (_runtime_entry(),),
        membership_resource_id="external_scope_membership",
        semantic_policies=policies,
    )

    resolved = runtime.resolve("科技")

    assert resolved.option.scope_code == "TMT"
    assert resolved.policy is not None
    assert resolved.policy.policy_id == "technology-v1"
