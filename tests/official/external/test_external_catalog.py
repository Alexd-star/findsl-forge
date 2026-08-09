import hashlib

import pytest

from findsl.official.external import (
    CatalogSnapshot,
    ExternalCatalog,
    ExternalCatalogError,
    IndustryMembership,
    InstrumentRule,
    ScopeMembership,
)


def _snapshot():
    payload = b"fixture"
    return CatalogSnapshot(
        snapshot_id="fixture-2026-07-13",
        source="fixture",
        source_url="https://example.invalid/catalog",
        retrieved_at="2026-07-13T12:00:00+08:00",
        as_of_date="2026-07-13",
        content_sha256=hashlib.sha256(payload).hexdigest(),
        license_note="test fixture",
        scope_memberships=(
            ScopeMembership(
                "concept",
                "BK001",
                "算力概念",
                ("算力", "AI算力"),
                1,
                "600000",
                "2026-01-01",
                None,
                0.8,
            ),
            ScopeMembership(
                "concept",
                "BK001",
                "算力概念",
                ("算力",),
                0,
                "000001",
                "2026-01-01",
                None,
                0.5,
            ),
        ),
        industry_memberships=(
            IndustryMembership(
                "CSRC-2012", "section", "C39", "计算机通信", 1, "600000", None, None
            ),
        ),
        instrument_rules=(
            InstrumentRule(1, "600000", "stock", False, None, None, "SSE trading rules"),
        ),
    )


def test_catalog_import_resolve_alias_and_effective_date(tmp_path):
    catalog = ExternalCatalog(tmp_path / "catalog.sqlite3")
    catalog.import_snapshot(_snapshot())

    rows = catalog.resolve_scope("ＡＩ 算力", as_of_date="2026-07-13")

    assert [row["tgtcode"] for row in rows] == ["600000", "000001"]
    assert rows[0]["scope_name"] == "算力概念"
    assert catalog.resolve_scope("算力", as_of_date="2025-12-31") == ()
    assert catalog.summary()["counts"] == {
        "snapshots": 1,
        "scope_membership": 2,
        "scope_alias": 3,
        "industry_membership": 1,
        "instrument_rule": 1,
    }
    inventory = catalog.snapshot_inventory()
    assert inventory[0]["snapshot_id"] == "fixture-2026-07-13"
    assert inventory[0]["scope_memberships"] == 2
    assert inventory[0]["industry_memberships"] == 1
    assert inventory[0]["instrument_rules"] == 1
    assert inventory[0]["license_note"] == "test fixture"


def test_catalog_duplicate_snapshot_requires_explicit_replace(tmp_path):
    catalog = ExternalCatalog(tmp_path / "catalog.sqlite3")
    catalog.import_snapshot(_snapshot())

    with pytest.raises(ExternalCatalogError, match="already exists"):
        catalog.import_snapshot(_snapshot())

    catalog.import_snapshot(_snapshot(), replace=True)
    assert catalog.summary()["counts"]["scope_membership"] == 2


def test_catalog_can_atomically_supersede_same_source_date_snapshot(tmp_path):
    catalog = ExternalCatalog(tmp_path / "catalog.sqlite3")
    catalog.import_snapshot(_snapshot())
    replacement = CatalogSnapshot(
        "fixture-2026-07-13-v2",
        "fixture",
        "https://example.invalid/catalog",
        "2026-07-13T13:00:00+08:00",
        "2026-07-13",
        "3" * 64,
        "replacement fixture",
        scope_memberships=(
            ScopeMembership(
                "concept", "BK002", "机器人", (), 0, "000002",
                "2026-01-01", None, None
            ),
        ),
    )

    catalog.import_snapshot(replacement, replace_source_date=True)

    summary = catalog.summary()
    assert [item["snapshot_id"] for item in summary["snapshots"]] == [
        "fixture-2026-07-13-v2"
    ]
    assert catalog.resolve_scope("算力") == ()
    assert catalog.resolve_scope("机器人")[0]["tgtcode"] == "000002"


def test_catalog_reads_latest_versioned_security_identities(tmp_path):
    catalog = ExternalCatalog(tmp_path / "catalog.sqlite3")
    identity = CatalogSnapshot(
        "identity-2026-07-13",
        "identity-source",
        "https://example.invalid/identities",
        "2026-07-13T00:00:00Z",
        "2026-07-13",
        "2" * 64,
        "fixture",
        scope_memberships=(
            ScopeMembership(
                "security", "SEC:0:000001", "平安银行", ("000001",), 0,
                "000001", "2026-07-13", None, None
            ),
        ),
    )
    catalog.import_snapshot(identity)

    rows = catalog.latest_security_identities("identity-source")

    assert rows == (
        {
            "mktcode": 0,
            "tgtcode": "000001",
            "scope_name": "平安银行",
            "snapshot_id": "identity-2026-07-13",
        },
    )
    with pytest.raises(ExternalCatalogError, match="unavailable"):
        catalog.latest_security_identities("missing-source")


def test_catalog_export_writes_doris_csvs_and_manifest(tmp_path):
    catalog = ExternalCatalog(tmp_path / "catalog.sqlite3")
    catalog.import_snapshot(_snapshot())

    manifest = catalog.export_doris(tmp_path / "doris")

    assert manifest["exports"]["scope_membership"]["rows"] == 2
    assert manifest["exports"]["industry_membership"]["rows"] == 1
    assert manifest["exports"]["instrument_rule"]["rows"] == 1
    assert (tmp_path / "doris" / "manifest.json").is_file()
    assert (tmp_path / "doris" / "scope_membership.csv").read_text(
        encoding="utf-8-sig"
    ).splitlines()[0] == (
        "snapshot_id,scope_code,mktcode,tgtcode,scope_type,scope_name,"
        "effective_from,effective_to,weight"
    )
    assert "\\N" in (tmp_path / "doris" / "scope_membership.csv").read_text(
        encoding="utf-8-sig"
    )

    runtime = catalog.export_runtime_manifest(tmp_path / "runtime.json")
    assert runtime["membership_resource_id"] == "external_scope_membership"
    assert {item["alias"] for item in runtime["entries"]} >= {
        "算力概念",
        "算力",
        "AI算力",
        "算力概念板块",
    }


def test_snapshot_rejects_empty_and_invalid_dates():
    with pytest.raises(ValueError, match="cannot be empty"):
        CatalogSnapshot(
            "empty",
            "fixture",
            "https://example.invalid",
            "2026-07-13T00:00:00Z",
            "2026-07-13",
            "0" * 64,
            "fixture",
        )
    with pytest.raises(ValueError, match="cannot be after"):
        ScopeMembership(
            "concept", "BK001", "算力", (), 1, "600000", "2026-02-01", "2026-01-01", None
        )


def test_runtime_manifest_filters_generic_aliases_that_change_index_semantics(tmp_path):
    snapshot = CatalogSnapshot(
        "index-fixture",
        "fixture-index",
        "https://example.invalid/index",
        "2026-07-13T00:00:00Z",
        "2026-07-13",
        "1" * 64,
        "fixture",
        scope_memberships=(
            ScopeMembership(
                "index",
                "399240",
                "金融指数",
                ("金融公司", "金融"),
                1,
                "600000",
                "2026-07-13",
                None,
                None,
            ),
            ScopeMembership(
                "index",
                "000142",
                "380稳定",
                ("上证380稳定",),
                1,
                "600000",
                "2026-07-13",
                None,
                None,
            ),
        ),
    )
    catalog = ExternalCatalog(tmp_path / "catalog.sqlite3")
    catalog.import_snapshot(snapshot)

    runtime = catalog.export_runtime_manifest(tmp_path / "runtime.json")
    aliases = {item["alias"] for item in runtime["entries"]}

    assert "金融公司" not in aliases
    assert "金融" not in aliases
    assert "金融指数" in aliases
    assert "上证380稳定" in aliases
