from dataclasses import dataclass

from findsl.official.external.industry_sync import (
    build_baostock_industry_snapshot,
)


@dataclass(frozen=True)
class _Row:
    update_date: str
    code: str
    name: str
    industry: str
    classification_system: str


class _Provider:
    source = "fixture"
    source_url = "https://example.invalid/industry"
    license_note = "fixture"

    @staticmethod
    def fetch():
        return (
            _Row("2026-07-13", "sh.600000", "浦发银行", "J66货币金融服务", "证监会行业分类"),
            _Row("2026-07-13", "sz.000001", "平安银行", "J66货币金融服务", "证监会行业分类"),
            _Row("2026-07-13", "sh.600001", "退市股", "", "证监会行业分类"),
        )


def test_baostock_industry_snapshot_is_single_valued_and_versioned():
    snapshot, classification = build_baostock_industry_snapshot(
        _Provider(), as_of_date="2026-07-13"
    )

    assert classification == "证监会行业分类"
    assert snapshot.snapshot_id.startswith("baostock-industry-2026-07-13-")
    assert len(snapshot.industry_memberships) == 2
    assert {item.industry_code for item in snapshot.industry_memberships} == {"J66"}
    assert {item.mktcode for item in snapshot.industry_memberships} == {0, 1}
