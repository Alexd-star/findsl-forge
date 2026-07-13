import json

from findsl.official.external.providers.sina import (
    SinaSectorConstituent,
    SinaSectorDefinition,
    SinaSectorProvider,
)
from findsl.official.external.sina_sync import build_sina_sector_snapshot


class _Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self):
        self.trust_env = True
        self.calls = 0

    def get(self, url, *, params, timeout, headers):
        self.calls += 1
        assert timeout > 0
        assert headers["User-Agent"]
        if "newFLJK" in url:
            value = "concept_1,测试概念,2,0,0,0,0,0,600000,0,0,0,浦发银行"
            return _Response(f"var data={json.dumps({'concept_1': value})}")
        if "StockCount" in url:
            return _Response("2")
        return _Response(
            "[{symbol:'sh600000',code:'600000',name:'浦发银行'},"
            "{symbol:'sz000001',code:'000001',name:'平安银行'}]"
        )


def test_sina_provider_parses_and_caches_sector_members(tmp_path):
    session = _Session()
    provider = SinaSectorProvider(session=session, cache_dir=tmp_path)

    sector = provider.list_sectors("concept")[0]
    members = provider.list_constituents(sector)

    assert sector == SinaSectorDefinition("concept", "concept_1", "测试概念")
    assert members == (
        SinaSectorConstituent("000001", "平安银行"),
        SinaSectorConstituent("600000", "浦发银行"),
    )
    assert session.trust_env is False
    calls = session.calls
    provider.list_sectors("concept")
    provider.list_constituents(sector)
    assert session.calls == calls


class _Provider:
    source = "sina-fixture"
    source_url = "https://example.invalid"
    license_note = "fixture"

    def list_sectors(self, sector_type):
        return {
            "concept": (SinaSectorDefinition("concept", "gn_1", "算力概念"),),
            "region": (SinaSectorDefinition("region", "area_1", "四川省"),),
            "industry": (SinaSectorDefinition("industry", "hy_1", "软件业"),),
        }[sector_type]

    def list_constituents(self, _sector):
        return (
            SinaSectorConstituent("600000", "浦发银行"),
            SinaSectorConstituent("000001", "平安银行"),
        )


def test_sina_snapshot_preserves_region_alias_and_industry_rows():
    result = build_sina_sector_snapshot(provider=_Provider(), as_of_date="2026-07-13")

    assert result.discovered_sectors == 3
    assert result.successful_sectors == 3
    assert len(result.snapshot.scope_memberships) == 6
    assert len(result.snapshot.industry_memberships) == 2
    region = next(
        item for item in result.snapshot.scope_memberships if item.scope_type == "region"
    )
    assert region.aliases == ("四川",)
