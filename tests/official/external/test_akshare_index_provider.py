import pandas as pd

from findsl.official.external.providers.indexes import (
    AkshareCsindexProvider,
    AkshareIndexProvider,
    IndexDefinition,
)


class _Definitions:
    def list_indices(self):
        return (
            IndexDefinition("csindex", "000913", "300医药", "沪深300医药卫生指数"),
        )


class _Akshare:
    @staticmethod
    def index_stock_cons(*, symbol):
        assert symbol in {"000913", "000063"}
        return pd.DataFrame(
            [
                {"品种代码": "600000", "品种名称": "浦发银行", "纳入日期": "2024-12-16"},
                {"品种代码": "000001", "品种名称": "平安银行", "纳入日期": "2025-06-16"},
            ]
        )

    @staticmethod
    def index_stock_info():
        return pd.DataFrame(
            [
                {
                    "index_code": "000063",
                    "display_name": "上证周期",
                    "publish_date": "2010-02-03",
                }
            ]
        )


def test_akshare_index_provider_keeps_third_party_provenance():
    provider = AkshareCsindexProvider(
        definitions_provider=_Definitions(), akshare_module=_Akshare()
    )
    index = provider.list_indices()[0]
    rows = provider.list_constituents(index)

    assert index.source == "akshare-eastmoney-index"
    assert [item.code for item in rows] == ["600000", "000001"]
    assert [item.effective_date for item in rows] == ["2024-12-16", "2025-06-16"]
    assert all(item.weight is None for item in rows)


def test_akshare_public_index_provider_uses_general_index_directory():
    provider = AkshareIndexProvider(akshare_module=_Akshare())

    index = provider.list_indices()[0]
    rows = provider.list_constituents(index)

    assert (index.code, index.name, index.source) == (
        "000063",
        "上证周期",
        "akshare-public-index",
    )
    assert [item.code for item in rows] == ["600000", "000001"]
