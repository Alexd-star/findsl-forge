from findsl.official.external.providers.eastmoney import BoardConstituent, BoardDefinition
from findsl.official.external.sync import (
    build_eastmoney_snapshot,
    build_full_eastmoney_snapshot,
)


class _Provider:
    source = "fixture"
    source_url = "https://example.invalid"
    license_note = "fixture"

    def list_boards(self, board_type):
        return {
            "concept": (BoardDefinition("concept", "BK1", "算力概念"),),
            "industry": (BoardDefinition("industry", "BK2", "白酒行业"),),
        }[board_type]

    def list_constituents(self, board):
        return (
            BoardConstituent("600000", "浦发银行", 1),
            BoardConstituent("000001", "平安银行", 2),
            BoardConstituent("700000", "腾讯", 3),
        )


def test_build_snapshot_matches_targets_and_preserves_unresolved():
    result = build_eastmoney_snapshot(
        ["算力", "白酒行业", "不存在范围"],
        provider=_Provider(),
        as_of_date="2026-07-13",
    )

    assert len(result.snapshot.scope_memberships) == 4
    assert len(result.snapshot.industry_memberships) == 2
    assert [item.target for item in result.matched] == ["算力", "白酒行业"]
    assert result.unresolved == ("不存在范围",)
    assert result.snapshot.content_sha256


def test_build_snapshot_uses_explicit_alias_and_retains_original_target():
    result = build_eastmoney_snapshot(
        ["算力相关"],
        provider=_Provider(),
        aliases={"算力相关": "算力概念"},
        as_of_date="2026-07-13",
    )

    assert result.matched[0].method == "alias_exact"
    assert result.matched[0].board.code == "BK1"
    assert {item.aliases for item in result.snapshot.scope_memberships} == {
        ("算力相关",)
    }


def test_exact_source_name_wins_when_canonical_alias_key_collides():
    class Provider(_Provider):
        def list_boards(self, board_type):
            return {
                "concept": (BoardDefinition("concept", "BK1", "白酒"),),
                "industry": (BoardDefinition("industry", "BK2", "白酒Ⅱ"),),
            }[board_type]

    result = build_eastmoney_snapshot(
        ["白酒", "白酒行业"],
        provider=Provider(),
        aliases={"白酒": "白酒Ⅱ"},
        as_of_date="2026-07-13",
    )

    assert [(item.target, item.board.code, item.method) for item in result.matched] == [
        ("白酒", "BK1", "source_exact"),
        ("白酒行业", "BK2", "alias_exact"),
    ]


def test_build_full_snapshot_attempts_every_discovered_board():
    result = build_full_eastmoney_snapshot(
        provider=_Provider(),
        as_of_date="2026-07-13",
    )

    assert result.discovered_boards == 2
    assert result.attempted_boards == 2
    assert result.unresolved == ()
    assert {(item.board.board_type, item.board.code) for item in result.matched} == {
        ("concept", "BK1"),
        ("industry", "BK2"),
    }
    assert result.to_dict()["successful_boards"] == 2
