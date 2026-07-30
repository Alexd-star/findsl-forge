import sqlite3

import pytest

from scripts.build_curated_scope_alias_snapshot import build_curated_rows


def test_curated_composite_intersects_versioned_memberships():
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


def test_curated_direct_mapping_rejects_abnormally_small_source():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE scope_membership (
             snapshot_id TEXT, scope_type TEXT, scope_code TEXT, scope_name TEXT,
             mktcode INTEGER, tgtcode TEXT, effective_from TEXT,
             effective_to TEXT, weight REAL
        )"""
    )
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


def test_curated_composite_rejects_abnormally_small_component():
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


def test_curated_composite_rejects_abnormally_small_result():
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
