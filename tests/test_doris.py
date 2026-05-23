from pathlib import Path

import pytest

from findsl.doris import render_doris_assets, write_doris_assets


DATA_DIR = Path("data/samples")


def test_render_doris_assets_contains_schema_prefix_and_smoke_sql():
    assets = render_doris_assets(DATA_DIR)
    assert "CREATE DATABASE IF NOT EXISTS `findsl_demo`" in assets.schema_sql
    assert "CREATE TABLE IF NOT EXISTS `dwd_stock_daily_quote`" in assets.schema_sql
    assert "CREATE TABLE IF NOT EXISTS `dwd_stock_daily_quote_prefix`" in assets.schema_sql
    assert "DUPLICATE KEY(`ts_code`, `trade_date`)" in assets.schema_sql
    assert assets.schema_sql.count("AUTO PARTITION BY RANGE (date_trunc(`trade_date`, 'month'))") == 5
    assert assets.schema_sql.count('"colocate_with" = "findsl_stock_by_ts"') == 5
    assert "DISTRIBUTED BY HASH(`ts_code`) BUCKETS 8" in assets.schema_sql
    assert "INSERT INTO `dwd_stock_daily_quote`" in assets.sample_data_sql
    assert "TRUNCATE TABLE `dwd_stock_daily_quote_prefix`" in assets.prefix_sql
    assert "`volume_sum_120` BIGINT" in assets.schema_sql
    assert "SUM(`volume`) OVER" in assets.prefix_sql
    assert "ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS `volume_sum_120`" in assets.prefix_sql
    assert "FROM `dwd_stock_daily_quote` AS base" in assets.prefix_sql
    assert "LEFT JOIN `dwd_stock_money_flow` AS src" in assets.prefix_sql
    assert "SUM(src.`main_net_inflow`) OVER" in assets.prefix_sql
    assert "dwd_stock_daily_quote_prefix" in assets.smoke_sql
    assert "Baseline window SQL" in assets.smoke_sql


def test_write_doris_assets(tmp_path):
    assets = write_doris_assets(tmp_path, DATA_DIR, database="findsl_test")
    for filename in assets.files():
        assert (tmp_path / filename).exists()
    assert "USE `findsl_test`" in (tmp_path / "01_schema.sql").read_text(encoding="utf-8")


def test_render_doris_assets_rejects_invalid_partition_granularity():
    with pytest.raises(ValueError, match="Unsupported Doris auto-partition granularity"):
        render_doris_assets(DATA_DIR, partition_granularity="month); DROP TABLE x; --")
