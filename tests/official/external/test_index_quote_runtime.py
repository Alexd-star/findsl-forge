import pytest

from findsl.official.external.runtime import (
    ExternalIndexQuoteCatalog,
    ExternalScopeRuntimeError,
)


def test_index_quote_runtime_resolves_versioned_scope_code():
    catalog = ExternalIndexQuoteCatalog.from_dict(
        {
            "schema_version": 1,
            "resource_id": "external_index_quote",
            "entries": [
                {
                    "scope_code": "000300",
                    "snapshot_id": "snapshot-1",
                    "source": "fixture",
                    "as_of_date": "2026-07-13",
                }
            ],
        }
    )

    assert catalog.resolve("000300").snapshot_id == "snapshot-1"
    with pytest.raises(KeyError):
        catalog.resolve("000905")


def test_index_quote_runtime_rejects_untracked_fields():
    with pytest.raises(ExternalScopeRuntimeError):
        ExternalIndexQuoteCatalog.from_dict(
            {
                "schema_version": 1,
                "resource_id": "external_index_quote",
                "entries": [{"scope_code": "000300", "snapshot_id": "x"}],
            }
        )
