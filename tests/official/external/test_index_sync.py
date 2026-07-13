from findsl.official.external.index_sync import build_index_snapshot
from findsl.official.external.providers.indexes import IndexConstituent, IndexDefinition


class _IndexProvider:
    source = "fixture-index"
    source_url = "https://example.invalid/index"
    license_note = "fixture"

    def list_indices(self):
        return (
            IndexDefinition(self.source, "000300", "沪深300", "沪深300指数"),
            IndexDefinition(self.source, "000688", "科创50", "上证科创板50成份指数"),
        )

    def list_constituents(self, index):
        return (
            IndexConstituent("600000", "浦发银行", 1.5, "2026-07-01"),
            IndexConstituent("000001", "平安银行", 1.0, "2026-07-01"),
        )


def test_index_sync_uses_official_weight_and_alias():
    result = build_index_snapshot(
        ["沪深300指数", "科创50", "不存在指数"],
        provider=_IndexProvider(),
        as_of_date="2026-07-13",
    )

    assert result is not None
    assert len(result.snapshot.scope_memberships) == 4
    assert result.snapshot.scope_memberships[0].weight == 1.5
    assert {item["target"] for item in result.matched} == {"沪深300指数", "科创50"}
    assert result.unresolved == ("不存在指数",)


def test_index_sync_does_not_fuzzy_match_generic_scope_to_index():
    class GenericProvider(_IndexProvider):
        def list_indices(self):
            return (
                IndexDefinition(self.source, "399999", "通用指数", "通用行业指数"),
            )

    result = build_index_snapshot(
        ["通用设备", "设备指数"],
        provider=GenericProvider(),
        aliases={"通用设备": "399999"},
        as_of_date="2026-07-13",
    )

    assert result is not None
    assert {item["target"] for item in result.matched} == {"通用设备"}
    assert result.unresolved == ("设备指数",)


def test_index_sync_accepts_curated_alphanumeric_index_code():
    class CniProvider(_IndexProvider):
        def list_indices(self):
            return (
                IndexDefinition(self.source, "CN2697", "中关村60R", "中关村60全收益指数"),
            )

    result = build_index_snapshot(
        ["中关村60指数R"],
        provider=CniProvider(),
        aliases={"中关村60指数r": "CN2697"},
        as_of_date="2026-07-13",
    )

    assert result is not None
    assert result.matched[0]["index_code"] == "CN2697"


def test_index_sync_rejects_suffix_stripped_generic_company_scope():
    class FinancialProvider(_IndexProvider):
        def list_indices(self):
            return (
                IndexDefinition(self.source, "399240", "金融指数", "金融指数"),
            )

    result = build_index_snapshot(
        ["金融公司"],
        provider=FinancialProvider(),
        as_of_date="2026-07-13",
    )

    assert result is None
