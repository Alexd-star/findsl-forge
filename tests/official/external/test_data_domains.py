from pathlib import Path

import pytest

from findsl.official.context import CompileContext
from findsl.official.external.data_domains import (
    DataDomainCatalog,
    DataDomainCatalogError,
)
from findsl.official.external.source_registry import ExternalSourceRegistry


REPO_ROOT = Path(__file__).resolve().parents[3]


def _catalog() -> DataDomainCatalog:
    sources = ExternalSourceRegistry.load(
        REPO_ROOT / "configs/official/external_source_registry.json"
    )
    return DataDomainCatalog.load(
        REPO_ROOT / "configs/official/data_domains.json",
        source_registry=sources,
    )


def test_data_domain_catalog_covers_every_indicator_domain() -> None:
    context = CompileContext.load(REPO_ROOT)
    bound = {
        indicator_domain
        for definition in context.data_domain_catalog.definitions()
        for indicator_domain in definition.indicator_domains
    }

    assert {item.domain for item in context.registry.definitions} <= bound
    assert context.data_domain_catalog.resolve("financial_statement").for_profile(
        "competition-v1"
    ).status == "not_loaded"
    assert context.data_domain_catalog.resolve("daily_market_quote").for_profile(
        "competition-official-only-v1"
    ).status == "available"


def test_data_domain_catalog_validates_provider_domain_capability() -> None:
    sources = ExternalSourceRegistry.load(
        REPO_ROOT / "configs/official/external_source_registry.json"
    )
    raw = {
        "schema_version": 1,
        "domains": [
            {
                "domain_id": "bad",
                "indicator_domains": [],
                "provider_domain_ids": ["financial_statement"],
                "description": "test",
                "granularity": "daily",
                "temporal_model": "historical_series",
                "primary_keys": ["id"],
                "quality_gates": ["non_empty"],
                "profiles": [
                    {
                        "profile_id": "competition-v1",
                        "status": "available",
                        "active_provider_ids": ["official-package"],
                        "candidate_provider_ids": [],
                        "reason": "test",
                    },
                    {
                        "profile_id": "competition-official-only-v1",
                        "status": "not_loaded",
                        "active_provider_ids": [],
                        "candidate_provider_ids": [],
                        "reason": "test",
                    },
                ],
            }
        ],
    }

    with pytest.raises(DataDomainCatalogError, match="does not declare"):
        DataDomainCatalog.from_dict(raw, source_registry=sources)


def test_profile_summary_does_not_label_optional_data_as_loaded() -> None:
    catalog = _catalog()
    official = {
        item["domain_id"]: item["profile"]["status"]
        for item in catalog.profile_summary("competition-official-only-v1")
    }

    assert official["financial_statement"] == "not_loaded"
    assert official["intraday_quote"] == "not_loaded"
    assert official["private_account"] == "private_required"
    assert official["technical_indicator"] == "derived"
