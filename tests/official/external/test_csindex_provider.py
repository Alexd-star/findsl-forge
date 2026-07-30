import pandas as pd

from findsl.official.external.providers.indexes import CsindexProvider, IndexDefinition


class _Response:
    content = b"fixture"


class _Http:
    def get(self, url):
        assert "000300" in url
        return _Response()


def test_csindex_provider_accepts_current_bilingual_constituent_headers(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "日期Date": 20260730,
                "成份券代码Constituent Code": 1,
                "成份券名称Constituent Name": "平安银行",
                "权重(%)weight": 0.345,
            },
            {
                "日期Date": 20260730,
                "成份券代码Constituent Code": 600000,
                "成份券名称Constituent Name": "浦发银行",
                "权重(%)weight": 0.2,
            },
        ]
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: frame)
    provider = CsindexProvider(http=_Http())

    rows = provider.list_constituents(
        IndexDefinition("csindex", "000300", "沪深300", "沪深300指数")
    )

    assert [item.code for item in rows] == ["000001", "600000"]
    assert [item.name for item in rows] == ["平安银行", "浦发银行"]
    assert [item.effective_date for item in rows] == ["2026-07-30", "2026-07-30"]
    assert [item.weight for item in rows] == [0.345, 0.2]
