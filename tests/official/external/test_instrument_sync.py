import json

from findsl.official.external.instrument_sync import build_official_stock_t0_snapshot


def test_official_stock_universe_builds_versioned_non_t0_rules(tmp_path):
    path = tmp_path / "securities.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"mktcode": 1, "tgtcode": "600000", "name": "浦发银行"},
                    {"mktcode": 0, "tgtcode": "200001", "name": "深证B"},
                    {"mktcode": 103, "tgtcode": "920001", "name": "北交所股票"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    snapshot = build_official_stock_t0_snapshot(path, as_of_date="2026-07-13")

    assert len(snapshot.instrument_rules) == 3
    assert not any(item.t0_eligible for item in snapshot.instrument_rules)
    assert snapshot.instrument_rules[1].instrument_type == "b_share"
