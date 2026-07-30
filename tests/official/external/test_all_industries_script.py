from pathlib import Path


def test_all_industries_sync_script_is_versioned_and_does_not_overwrite_snapshots():
    source = Path("scripts/sync_all_industries.py").read_text(encoding="utf-8")

    assert "provider.list_boards(\"industry\")" in source
    assert "catalog.import_snapshot(result.snapshot)" in source
    assert "replace=True" not in source
    assert "catalog.export_runtime_manifest" in source


def test_ths_sync_fails_closed_unless_partial_import_is_explicitly_allowed():
    source = Path("scripts/sync_ths_concepts.py").read_text(encoding="utf-8")

    assert '"--allow-partial"' in source
    assert 'report["imported"] = not failures or args.allow_partial' in source
    assert 'raise SystemExit(2)' in source
