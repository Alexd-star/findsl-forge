from pathlib import Path


def test_all_industries_sync_script_is_versioned_and_does_not_overwrite_snapshots():
    source = Path("scripts/sync_all_industries.py").read_text(encoding="utf-8")

    assert "provider.list_boards(\"industry\")" in source
    assert "catalog.import_snapshot(result.snapshot)" in source
    assert "replace=True" not in source
    assert "catalog.export_runtime_manifest" in source
