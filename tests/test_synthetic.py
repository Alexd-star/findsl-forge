import csv
from pathlib import Path

from findsl.synthetic import write_synthetic_dataset


def test_write_synthetic_dataset_is_reproducible(tmp_path):
    first = write_synthetic_dataset(tmp_path / "first", stock_count=4, day_count=6, seed=7)
    second = write_synthetic_dataset(tmp_path / "second", stock_count=4, day_count=6, seed=7)

    assert first.row_count == 24
    assert second.row_count == 24
    for logical_name in first.files():
        assert first.files()[logical_name].read_text(encoding="utf-8") == second.files()[
            logical_name
        ].read_text(encoding="utf-8")


def test_write_synthetic_dataset_has_expected_tables_and_columns(tmp_path):
    dataset = write_synthetic_dataset(tmp_path / "scale", stock_count=3, day_count=2)

    assert set(dataset.files()) == {"daily_quote", "money_flow", "stock_universe"}
    with Path(dataset.files()["daily_quote"]).open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 6
    assert set(rows[0]) == {"ts_code", "trade_date", "close", "turnover_rate", "volume"}
    assert rows[0]["ts_code"] == "000001.SH"
