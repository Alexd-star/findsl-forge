from pathlib import Path

import pytest

from findsl.official.external.adapters import (
    DomainAdapterRegistry,
    DomainAdapterRequest,
    DomainAdapterRunner,
    LocalTabularDomainAdapter,
)
from findsl.official.external.admission import DomainSnapshotAdmissionError
from findsl.official.external.contracts import DomainTableContractCatalog
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
    contracts = DomainTableContractCatalog.load(
        REPO_ROOT / "configs/official/domain_table_contracts.json"
    )
    return sources, domains, contracts


def test_financial_contract_requires_point_in_time_and_metric_columns():
    _, _, contracts = _catalogs()

    accepted = contracts.audit(
        "financial_statement",
        (
            "mktcode",
            "tgtcode",
            "report_period",
            "announcement_date",
            "version",
            "currency",
            "unit",
            "revenue",
        ),
    )
    rejected = contracts.audit(
        "financial_statement",
        ("mktcode", "tgtcode", "report_period", "revenue"),
    )

    assert accepted["status"] == "PASS"
    assert accepted["matched_variant"] == "point_in_time_statement"
    assert rejected["status"] == "REJECTED"
    assert "announcement_date" in rejected["variants"][0][
        "missing_required_columns"
    ]


def test_adapter_rejects_financial_snapshot_without_announcement_time(
    tmp_path: Path,
):
    data = tmp_path / "financial.csv"
    data.write_text(
        "mktcode,tgtcode,report_period,version,currency,unit,revenue\n"
        "1,600000,2025-12-31,1,CNY,CNY,100\n",
        encoding="utf-8",
    )
    sources, domains, contracts = _catalogs()
    adapter = LocalTabularDomainAdapter(
        provider_id="tushare-optional",
        domain_id="financial_statement",
        source="tushare",
        source_url="https://tushare.pro/",
        license_note="Test fixture; production use requires a licensed snapshot.",
        temporal_model="effective_dated",
        data_path=data,
        data_format="csv",
        license_accepted=True,
    )
    runner = DomainAdapterRunner(
        adapters=DomainAdapterRegistry((adapter,)),
        data_domains=domains,
        sources=sources,
        contracts=contracts,
    )

    with pytest.raises(DomainSnapshotAdmissionError, match="table variant"):
        runner.fetch_and_audit(
            "tushare-optional",
            DomainAdapterRequest(
                "financial_statement", "competition-v1", "2026-08-13"
            ),
        )


def test_fund_index_and_scope_contracts_expose_versioned_variants():
    _, _, contracts = _catalogs()

    assert {item.variant_id for item in contracts.resolve("fund_reference")} == {
        "fund_identity",
        "fund_portfolio",
    }
    assert {item.variant_id for item in contracts.resolve("index_reference")} == {
        "index_identity",
        "index_membership",
    }
    assert contracts.resolve("scope_membership")[0].temporal_columns == (
        "snapshot_id",
        "effective_from",
    )


def test_fund_identity_variant_is_not_rejected_by_portfolio_primary_keys(
    tmp_path: Path,
):
    data = tmp_path / "fund_identity.csv"
    data.write_text(
        "fund_code,fund_name,fund_type,effective_from,exchange\n"
        "510300,沪深300ETF,ETF,2026-08-13,SSE\n",
        encoding="utf-8",
    )
    sources, domains, contracts = _catalogs()
    adapter = LocalTabularDomainAdapter(
        provider_id="tushare-optional",
        domain_id="fund_reference",
        source="tushare",
        source_url="https://tushare.pro/",
        license_note="Test fixture; production use requires a licensed snapshot.",
        temporal_model="effective_dated",
        data_path=data,
        data_format="csv",
        license_accepted=True,
    )
    runner = DomainAdapterRunner(
        adapters=DomainAdapterRegistry((adapter,)),
        data_domains=domains,
        sources=sources,
        contracts=contracts,
    )

    _, report = runner.fetch_and_audit(
        "tushare-optional",
        DomainAdapterRequest("fund_reference", "competition-v1", "2026-08-13"),
    )

    assert report["passed"] is True
    assert report["status"] == "CANDIDATE"
    assert report["table_contract"]["matched_variant"] == "fund_identity"
