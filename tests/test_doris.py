from pathlib import Path

from findsl.doris import render_doris_assets, write_doris_assets


DATA_DIR = Path("data/samples")


def test_render_doris_assets_contains_schema_prefix_and_smoke_sql():
    assets = render_doris_assets(DATA_DIR)
    assert "CREATE DATABASE IF NOT EXISTS `findsl_demo`" in assets.schema_sql
    assert "CREATE TABLE IF NOT EXISTS `dwd_stock_daily_quote`" in assets.schema_sql
    assert "CREATE TABLE IF NOT EXISTS `dwd_stock_daily_quote_prefix`" in assets.schema_sql
    assert "DUPLICATE KEY(`ts_code`, `trade_date`)" in assets.schema_sql
    assert "INSERT INTO `dwd_stock_daily_quote`" in assets.sample_data_sql
    assert "TRUNCATE TABLE `dwd_stock_daily_quote_prefix`" in assets.prefix_sql
    assert "SUM(`volume`) OVER" in assets.prefix_sql
    assert "dwd_stock_daily_quote_prefix" in assets.smoke_sql
    assert "Baseline window SQL" in assets.smoke_sql


def test_write_doris_assets(tmp_path):
    assets = write_doris_assets(tmp_path, DATA_DIR, database="findsl_test")
    for filename in assets.files():
        assert (tmp_path / filename).exists()
    assert "USE `findsl_test`" in (tmp_path / "01_schema.sql").read_text(encoding="utf-8")
