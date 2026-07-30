from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.models import CatalogSnapshot, ScopeMembership


def _snapshot(snapshot_id: str, scope_code: str) -> CatalogSnapshot:
    return CatalogSnapshot(
        snapshot_id=snapshot_id,
        source="csindex",
        source_url="https://www.csindex.com.cn/",
        retrieved_at="2026-07-30T00:00:00+00:00",
        as_of_date="2026-07-30",
        content_sha256="a" * 64 if scope_code == "000300" else "b" * 64,
        license_note="fixture",
        scope_memberships=(
            ScopeMembership(
                scope_type="index",
                scope_code=scope_code,
                scope_name=scope_code,
                aliases=(scope_code,),
                mktcode=1,
                tgtcode="600000",
                effective_from=None,
                effective_to=None,
                weight=None,
                match_method="exact",
            ),
        ),
    )


def test_targeted_csindex_imports_from_the_same_day_coexist(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.sqlite3"
    catalog = ExternalCatalog(catalog_path)
    catalog.import_snapshot(_snapshot("snapshot-300", "000300"), replace=True)
    catalog.import_snapshot(_snapshot("snapshot-972", "000972"), replace=True)

    manifest = catalog.export_runtime_manifest(tmp_path / "runtime.json")
    index_codes = {
        item["scope_code"]
        for item in manifest["entries"]
        if item["source"] == "csindex"
    }

    assert {"000300", "000972"} <= index_codes


def test_targeted_sync_script_uses_snapshot_replace_not_source_date_replace():
    script = Path(__file__).parents[3] / "scripts" / "sync_csindex_constituents.py"
    source = script.read_text(encoding="utf-8")

    assert "import_snapshot(result.snapshot, replace=True)" in source
    assert "replace_source_date=True" not in source
