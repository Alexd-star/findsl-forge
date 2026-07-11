import json

import pytest

from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.statistics import (
    default_physical_statistics,
    PhysicalStatisticsError,
    PhysicalStatisticsSnapshot,
)


def _payload(catalog, resources=None):
    return {
        "schema_version": 1,
        "catalog_sha256": catalog.fingerprint,
        "collected_at": "2026-07-11T16:00:00+08:00",
        "doris_version": "4.1.0",
        "resources": resources
        or [
            {
                "resource_id": "official_basic",
                "row_count": 13650347,
                "data_size_bytes": 411096137,
                "row_count_available": True,
            }
        ],
    }


def test_statistics_snapshot_loads_real_counts_and_serializes_deterministically(tmp_path):
    catalog = default_physical_catalog()
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_payload(catalog)), encoding="utf-8")

    snapshot = PhysicalStatisticsSnapshot.load(path, catalog)

    stats = snapshot.resource("official_basic")
    assert stats.row_count == 13650347
    assert stats.data_size_bytes == 411096137
    assert stats.row_count_available is True
    assert snapshot.canonical_json() == snapshot.canonical_json()


@pytest.mark.parametrize(
    "resources",
    [
        [
            {"resource_id": "missing", "row_count": 1, "data_size_bytes": 1, "row_count_available": True},
        ],
        [
            {"resource_id": "official_basic", "row_count": 1, "data_size_bytes": 1, "row_count_available": True},
            {"resource_id": "official_basic", "row_count": 2, "data_size_bytes": 2, "row_count_available": True},
        ],
        [
            {"resource_id": "official_basic", "row_count": -1, "data_size_bytes": 1, "row_count_available": True},
        ],
    ],
)
def test_statistics_snapshot_rejects_unknown_duplicate_or_negative_resources(tmp_path, resources):
    catalog = default_physical_catalog()
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_payload(catalog, resources)), encoding="utf-8")

    with pytest.raises(PhysicalStatisticsError):
        PhysicalStatisticsSnapshot.load(path, catalog)


def test_statistics_snapshot_rejects_catalog_fingerprint_mismatch(tmp_path):
    catalog = default_physical_catalog()
    payload = _payload(catalog)
    payload["catalog_sha256"] = "0" * 64
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PhysicalStatisticsError, match="catalog fingerprint"):
        PhysicalStatisticsSnapshot.load(path, catalog)


def test_default_statistics_snapshot_is_bound_to_all_catalog_resources():
    catalog = default_physical_catalog()
    snapshot = default_physical_statistics(catalog)

    assert snapshot.catalog_sha256 == catalog.fingerprint
    assert {item.resource_id for item in snapshot.resources} == {
        "official_basic",
        "official_ext",
        "official_security",
        "official_technical",
    }
