from findsl.official.external.policy import ScopeSemanticPolicyCatalog
from scripts.collect_phase48_scope_policy_evidence import _reference_members_sql


def _catalog(*entries):
    return ScopeSemanticPolicyCatalog.from_dict(
        {
            "schema_version": 1,
            "policy_set_id": "fixture-v1",
            "profile": "competition",
            "allowed_risk_levels": ["low"],
            "entries": list(entries),
        }
    )


def _common(policy_id, alias, kind, **specific):
    return {
        "policy_id": policy_id,
        "aliases": [alias],
        "resolution_kind": kind,
        "scope_name": alias,
        "minimum_member_count": 1,
        "maximum_member_count": 10,
        "semantic_basis": "official_rule",
        "confidence": "high",
        "risk_level": "low",
        "review_status": "approved",
        "effective_from": "2026-01-01",
        "rationale": "fixture",
        "rationale_urls": ["https://example.test/policy"],
        "data_boundary": "fixture",
        **specific,
    }


def test_reference_sql_uses_original_exact_scope_snapshot():
    policy = _catalog(
        _common(
            "exact-v1",
            "科技",
            "exact_scope",
            target={"source_snapshot_id": "source-v1", "scope_code": "TMT"},
        )
    ).policies[0]

    sql = _reference_members_sql(policy)

    assert "source-v1" in sql
    assert "TMT" in sql
    assert "curated" not in sql


def test_reference_sql_excludes_st_from_s_prefix_rule():
    policy = _catalog(
        _common(
            "s-rule-v1",
            "S板",
            "security_name_regex",
            source_snapshot_id="identity-v1",
            selector={"field": "scope_name", "operator": "regex", "value": "^S(?!T)"},
        )
    ).policies[0]

    sql = _reference_members_sql(policy)

    assert "scope_name LIKE 'S%'" in sql
    assert "scope_name NOT LIKE 'ST%'" in sql


def test_reference_sql_rebuilds_intersection_from_both_source_snapshots():
    policy = _catalog(
        _common(
            "set-v1",
            "上海水利工程",
            "set_operation",
            operation="intersection",
            components=[
                {
                    "source_snapshot_id": "shanghai-v1",
                    "scope_code": "SH",
                    "minimum_member_count": 1,
                },
                {
                    "source_snapshot_id": "water-v1",
                    "scope_code": "WATER",
                    "minimum_member_count": 1,
                },
            ],
        )
    ).policies[0]

    sql = _reference_members_sql(policy)

    assert "shanghai-v1" in sql
    assert "water-v1" in sql
    assert " INTERSECT " in sql
