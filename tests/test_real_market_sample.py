from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from findsl.equivalence import verify_sql_equivalence


DATA_DIR = Path("data/real_samples/eastmoney_a_share_sample")


def _load_fetcher():
    script = Path("scripts/fetch_real_market_sample.py")
    spec = importlib.util.spec_from_file_location("fetch_real_market_sample", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_eastmoney_klines_maps_quote_fields():
    module = _load_fetcher()
    payload = {
        "rc": 0,
        "data": {
            "klines": [
                "2024-01-02,7.83,7.65,7.86,7.65,1158366,1075742252.45,2.68,-2.30,-0.18,0.60"
            ]
        },
    }
    stock = module.StockSource(ts_code="000001.SZ", secid="0.000001", name="平安银行", market="A")

    rows = module.parse_eastmoney_klines(payload, stock)

    assert rows == [
        {
            "ts_code": "000001.SZ",
            "trade_date": "2024-01-02",
            "close": "7.65",
            "turnover_rate": "0.6",
            "volume": "1158366",
            "market": "A",
        }
    ]


def test_real_market_sample_files_exist_and_are_documented():
    required = {
        "README.md",
        "source_metadata.json",
        "daily_quote.csv",
        "stock_universe.csv",
        "money_flow.csv",
        "queries.jsonl",
    }

    assert required <= {path.name for path in DATA_DIR.iterdir()}
    metadata = (DATA_DIR / "source_metadata.json").read_text(encoding="utf-8")
    assert "Eastmoney public historical K-line endpoint" in metadata
    assert "neutral zero-valued placeholder" in metadata


def test_real_market_quote_dsl_matches_reference():
    result = verify_sql_equivalence(
        'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)',
        DATA_DIR,
    )

    assert result.passed
    assert result.sql_row_count > 0
