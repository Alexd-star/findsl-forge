import sqlite3

import pytest

from findsl.official.external.policy import ScopeSemanticPolicyCatalog
from scripts.build_curated_scope_alias_snapshot import (
    build_curated_rows,
    build_semantic_policy_rows,
)


@pytest.fixture
def membership_connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE scope_membership (
             snapshot_id TEXT, scope_type TEXT, scope_code TEXT, scope_name TEXT,
             mktcode INTEGER, tgtcode TEXT, effective_from TEXT,
             effective_to TEXT, weight REAL
        )"""
    )
    try:
        yield connection
    finally:
        connection.close()


def test_curated_composite_intersects_versioned_memberships(membership_connection):
    connection = membership_connection
    connection.executemany(
        "INSERT INTO scope_membership VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("region-v1", "region", "R1", "宁夏", 0, "000001", "2026-01-01", None, None),
            ("region-v1", "region", "R1", "宁夏", 0, "000002", "2026-01-01", None, None),
            ("compute-v1", "concept", "C1", "算力", 0, "000002", "2026-01-01", None, None),
            ("compute-v1", "concept", "C1", "算力", 1, "600000", "2026-01-01", None, None),
        ],
    )
    config = {
        "mappings": [
            {
                "alias": "宁夏算力概念",
                "scope_name": "宁夏算力概念",
                "operation": "intersection",
                "components": [
                    {"source_snapshot_id": "region-v1", "scope_code": "R1"},
                    {"source_snapshot_id": "compute-v1", "scope_code": "C1"},
                ],
                "reason": "fixture",
            }
        ]
    }

    rows, audit = build_curated_rows(config, connection, "2026-07-30")

    assert [(item.mktcode, item.tgtcode) for item in rows] == [(0, "000002")]
    assert rows[0].scope_type == "composite"
    assert rows[0].scope_code.startswith("CURATED:")
    assert audit[0]["operation"] == "intersection"
    assert audit[0]["component_member_counts"] == [2, 2]


def test_curated_direct_mapping_rejects_abnormally_small_source(membership_connection):
    connection = membership_connection
    connection.execute(
        "INSERT INTO scope_membership VALUES (?,?,?,?,?,?,?,?,?)",
        ("index-v1", "index", "000300", "沪深300", 0, "000001", None, None, None),
    )
    config = {
        "mappings": [
            {
                "alias": "沪深300港元净收益指数",
                "scope_code": "000300",
                "source_snapshot_id": "index-v1",
                "minimum_member_count": 250,
                "reason": "fixture",
            }
        ]
    }

    with pytest.raises(ValueError, match="below its minimum member count"):
        build_curated_rows(config, connection, "2026-07-30")


def test_curated_composite_rejects_abnormally_small_component(membership_connection):
    connection = membership_connection
    connection.executemany(
        "INSERT INTO scope_membership VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("left-v1", "concept", "L1", "左侧", 0, "000001", None, None, None),
            ("right-v1", "concept", "R1", "右侧", 0, "000001", None, None, None),
        ],
    )
    config = {
        "mappings": [
            {
                "alias": "受控交集",
                "operation": "intersection",
                "components": [
                    {
                        "source_snapshot_id": "left-v1",
                        "scope_code": "L1",
                        "minimum_member_count": 2,
                    },
                    {"source_snapshot_id": "right-v1", "scope_code": "R1"},
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="component is below its minimum member count"):
        build_curated_rows(config, connection, "2026-07-30")


def test_curated_composite_rejects_abnormally_small_result(membership_connection):
    connection = membership_connection
    connection.executemany(
        "INSERT INTO scope_membership VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("left-v1", "concept", "L1", "左侧", 0, "000001", None, None, None),
            ("left-v1", "concept", "L1", "左侧", 0, "000002", None, None, None),
            ("right-v1", "concept", "R1", "右侧", 0, "000001", None, None, None),
            ("right-v1", "concept", "R1", "右侧", 0, "000003", None, None, None),
        ],
    )
    config = {
        "mappings": [
            {
                "alias": "受控交集",
                "operation": "intersection",
                "minimum_member_count": 2,
                "components": [
                    {"source_snapshot_id": "left-v1", "scope_code": "L1"},
                    {"source_snapshot_id": "right-v1", "scope_code": "R1"},
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="result is below its minimum member count"):
        build_curated_rows(config, connection, "2026-07-30")


def _policy_catalog(*entries):
    return ScopeSemanticPolicyCatalog.from_dict(
        {
            "schema_version": 1,
            "policy_set_id": "fixture-v1",
            "profile": "competition",
            "allowed_risk_levels": ["low", "medium"],
            "entries": list(entries),
        }
    )


def _policy_entry(policy_id, alias, kind, **specific):
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


def _policy_connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE scope_membership (
             snapshot_id TEXT, scope_type TEXT, scope_code TEXT, scope_name TEXT,
             mktcode INTEGER, tgtcode TEXT, effective_from TEXT,
             effective_to TEXT, weight REAL
        )"""
    )
    connection.executemany(
        "INSERT INTO scope_membership VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("concept-v1", "concept", "C1", "科技", 0, "000001", None, None, None),
            ("concept-v1", "concept", "C1", "科技", 0, "000002", None, None, None),
            ("identity-v1", "security", "SEC:1", "S佳通", 1, "600182", None, None, None),
            ("identity-v1", "security", "SEC:2", "ST样本", 0, "000003", None, None, None),
            ("left-v1", "concept", "L1", "左", 0, "000001", None, None, None),
            ("left-v1", "concept", "L1", "左", 0, "000002", None, None, None),
            ("right-v1", "concept", "R1", "右", 0, "000002", None, None, None),
            ("right-v1", "concept", "R1", "右", 1, "600000", None, None, None),
        ],
    )
    return connection


@pytest.fixture
def policy_connection():
    connection = _policy_connection()
    try:
        yield connection
    finally:
        connection.close()


def test_semantic_policy_builder_supports_exact_rule_and_set_operation(policy_connection):
    connection = policy_connection
    catalog = _policy_catalog(
        _policy_entry(
            "exact-v1",
            "科技范围",
            "exact_scope",
            target={"source_snapshot_id": "concept-v1", "scope_code": "C1"},
        ),
        _policy_entry(
            "s-rule-v1",
            "S板",
            "security_name_regex",
            source_snapshot_id="identity-v1",
            selector={"field": "scope_name", "operator": "regex", "value": "^S(?!T)"},
        ),
        _policy_entry(
            "set-v1",
            "受控交集",
            "set_operation",
            operation="intersection",
            components=[
                {
                    "source_snapshot_id": "left-v1",
                    "scope_code": "L1",
                    "minimum_member_count": 2,
                },
                {
                    "source_snapshot_id": "right-v1",
                    "scope_code": "R1",
                    "minimum_member_count": 2,
                },
            ],
        ),
    )

    rows, audit = build_semantic_policy_rows(catalog, connection, "2026-08-01")

    by_alias = {item["aliases"][0]: item for item in audit}
    assert by_alias["科技范围"]["member_count"] == 2
    assert by_alias["S板"]["matched_security_names"] == ["S佳通"]
    assert by_alias["受控交集"]["member_count"] == 1
    assert {(row.scope_name, row.tgtcode) for row in rows} >= {
        ("S板", "600182"),
        ("受控交集", "000002"),
    }


def test_semantic_policy_builder_rejects_result_above_maximum(policy_connection):
    connection = policy_connection
    entry = _policy_entry(
        "exact-v1",
        "科技范围",
        "exact_scope",
        target={"source_snapshot_id": "concept-v1", "scope_code": "C1"},
    )
    entry["maximum_member_count"] = 1
    catalog = _policy_catalog(entry)

    with pytest.raises(ValueError, match="exceeds its maximum member count"):
        build_semantic_policy_rows(catalog, connection, "2026-08-01")
