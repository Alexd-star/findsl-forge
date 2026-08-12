from pathlib import Path

import pytest

from findsl.official.external.adapters import (
    DomainAdapterError,
    DomainAdapterRegistry,
    DomainAdapterRequest,
    DomainAdapterRunner,
    LocalTabularDomainAdapter,
)
from findsl.official.external.admission import DomainSnapshotAdmissionError
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


def _adapter(path: Path, *, license_accepted: bool = True):
    return LocalTabularDomainAdapter(
        provider_id="official-package",
        domain_id="daily_market_quote",
        source="competition-official-package",
        source_url="https://fintechpf.yunzhengdata.com/",
        license_note="Organizer-supplied competition data",
        temporal_model="historical_series",
        data_path=path,
        data_format="csv",
        license_accepted=license_accepted,
    )


def test_local_domain_adapter_is_fetchable_admitted_and_versioned(tmp_path: Path) -> None:
    data = tmp_path / "quotes.csv"
    data.write_text(
        "mktcode,tgtcode,bizdate,close\n1,600000,2026-04-14,10.1\n",
        encoding="utf-8",
    )
    sources, domains = _catalogs()
    runner = DomainAdapterRunner(
        adapters=DomainAdapterRegistry((_adapter(data),)),
        data_domains=domains,
        sources=sources,
    )

    artifact, report = runner.fetch_and_audit(
        "official-package",
        DomainAdapterRequest(
            "daily_market_quote",
            "competition-v1",
            "2026-04-14",
        ),
    )

    assert report["status"] == "ACTIVE_READY"
    assert artifact.manifest.row_count == 1
    assert artifact.manifest.snapshot_id.startswith(
        "official-package-2026-04-14-"
    )
    assert artifact.manifest.columns == (
        "mktcode",
        "tgtcode",
        "bizdate",
        "close",
    )


def test_adapter_registry_rejects_duplicate_provider_domain_pair(tmp_path: Path) -> None:
    data = tmp_path / "quotes.csv"
    data.write_text(
        "mktcode,tgtcode,bizdate\n1,600000,2026-04-14\n",
        encoding="utf-8",
    )
    adapter = _adapter(data)

    with pytest.raises(DomainAdapterError, match="duplicate"):
        DomainAdapterRegistry((adapter, adapter))


def test_candidate_data_cannot_bypass_license_admission(tmp_path: Path) -> None:
    data = tmp_path / "quotes.csv"
    data.write_text(
        "mktcode,tgtcode,bizdate\n1,600000,2026-04-14\n",
        encoding="utf-8",
    )
    sources, domains = _catalogs()
    runner = DomainAdapterRunner(
        adapters=DomainAdapterRegistry((_adapter(data, license_accepted=False),)),
        data_domains=domains,
        sources=sources,
    )

    with pytest.raises(DomainSnapshotAdmissionError, match="license"):
        runner.fetch_and_audit(
            "official-package",
            DomainAdapterRequest(
                "daily_market_quote",
                "competition-v1",
                "2026-04-14",
            ),
        )
