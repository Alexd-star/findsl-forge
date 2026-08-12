from pathlib import Path

from findsl.official.external.admission import (
    DomainSnapshotManifest,
    audit_domain_snapshot,
)
from findsl.official.external.data_domains import DataDomainCatalog
from findsl.official.external.source_registry import ExternalSourceRegistry


REPO_ROOT = Path(__file__).resolve().parents[3]


def _catalogs():
    sources = ExternalSourceRegistry.load(
        REPO_ROOT / "configs/official/external_source_registry.json"
    )
    domains = DataDomainCatalog.load(
        REPO_ROOT / "configs/official/data_domains.json",
        source_registry=sources,
    )
    return sources, domains


def _financial_manifest(**overrides):
    raw = {
        "schema_version": 1,
        "provider_id": "tushare-optional",
        "domain_id": "financial_statement",
        "profile_id": "competition-v1",
        "snapshot_id": "financial-2026q1-example",
        "source_uri": "file:///restricted/financial-2026q1.parquet",
        "retrieved_at": "2026-08-13T00:00:00+08:00",
        "as_of_date": "2026-08-13",
        "content_sha256": "a" * 64,
        "row_count": 100,
        "columns": [
            "mktcode",
            "tgtcode",
            "report_period",
            "announcement_date",
            "version",
            "revenue",
        ],
        "temporal_model": "effective_dated",
        "license_accepted": True,
    }
    raw.update(overrides)
    return DomainSnapshotManifest.from_dict(raw)


def test_candidate_financial_snapshot_passes_structure_but_requires_promotion():
    sources, domains = _catalogs()

    report = audit_domain_snapshot(
        _financial_manifest(),
        data_domains=domains,
        sources=sources,
    )

    assert report["passed"] is True
    assert report["status"] == "CANDIDATE"
    assert "promotion" in report["warnings"][0]


def test_snapshot_missing_point_in_time_key_is_rejected():
    sources, domains = _catalogs()
    manifest = _financial_manifest(
        columns=["mktcode", "tgtcode", "report_period", "revenue"]
    )

    report = audit_domain_snapshot(
        manifest,
        data_domains=domains,
        sources=sources,
    )

    assert report["passed"] is False
    assert report["status"] == "REJECTED"
    assert "announcement_date" in report["errors"][0]


def test_snapshot_with_secret_in_source_uri_is_rejected_before_admission():
    try:
        _financial_manifest(source_uri="https://example.com/data?token=secret")
    except ValueError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("credential-bearing snapshot URI must be rejected")
