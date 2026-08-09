from pathlib import Path

import pytest

from findsl.official.external.source_registry import (
    ExternalSourceRegistry,
    ExternalSourceRegistryError,
)
from findsl.official.external.providers import EastmoneyBoardProvider


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_source_registry_covers_current_snapshot_sources() -> None:
    registry = ExternalSourceRegistry.load(
        REPO_ROOT / "configs/official/external_source_registry.json"
    )
    expected = {
        "akshare-eastmoney-index",
        "akshare-public-index",
        "akshare-security-identity",
        "baidu-related-block",
        "baostock",
        "cnindex",
        "csindex",
        "curated-scope-alias",
        "eastmoney",
        "sina-finance",
        "sse-szse-bse",
    }

    assert expected <= {entry.source for entry in registry.entries()}
    assert registry.resolve("official-package").authority_level == "competition_official"
    assert registry.resolve("tushare-optional").redistribution == "not_redistributed"


def test_registry_validates_provider_provenance_contract() -> None:
    registry = ExternalSourceRegistry.load(
        REPO_ROOT / "configs/official/external_source_registry.json"
    )
    provider = EastmoneyBoardProvider()

    entry = registry.assert_provider("eastmoney", provider)

    assert entry.temporal_model == "current_snapshot"


def test_registry_rejects_provider_metadata_mismatch() -> None:
    registry = ExternalSourceRegistry.load(
        REPO_ROOT / "configs/official/external_source_registry.json"
    )

    class WrongProvider:
        source = "eastmoney"
        source_url = "https://example.invalid/"
        license_note = "test"

    with pytest.raises(ExternalSourceRegistryError, match="URL mismatch"):
        registry.assert_provider("eastmoney", WrongProvider())
