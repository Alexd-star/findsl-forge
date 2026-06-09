from pathlib import Path


OFFICIAL_DORIS_DIR = Path("deploy/doris/official")


def test_official_doris_assets_are_present_and_target_real_tables():
    schema = (OFFICIAL_DORIS_DIR / "01_schema.sql").read_text(encoding="utf-8")
    stream_load = (OFFICIAL_DORIS_DIR / "02_stream_load.md").read_text(encoding="utf-8")
    smoke = (OFFICIAL_DORIS_DIR / "03_smoke_queries.sql").read_text(encoding="utf-8")
    feature = (OFFICIAL_DORIS_DIR / "04_feature_tables.sql").read_text(encoding="utf-8")

    assert "CREATE DATABASE IF NOT EXISTS newzl" in schema
    assert "CREATE TABLE IF NOT EXISTS newzl.hsj_stock_hq_basic" in schema
    assert "UNIQUE KEY(mktcode, tgtcode, bizdate)" in schema
    assert "quantRatio INTEGER" in schema
    assert '"enable_unique_key_merge_on_write" = "true"' in schema

    assert "Stream Load" in stream_load
    assert "hsj_stock_code_info.csv" in stream_load
    assert "hsj_stock_hq_basic.csv" in stream_load
    assert "hsj_stock_hq_ext.csv" in stream_load
    assert "_stream_load" in stream_load

    assert "SELECT COUNT(*) AS hq_basic_rows" in smoke
    assert "EXPLAIN" in smoke
    assert "ROW_NUMBER() OVER" in smoke

    assert "hsj_stock_hq_basic_prefix" in feature
    assert "SUM(base.volume) OVER" in feature
    assert "hsj_stock_hq_ext_prefix" in feature
    assert "SUM(COALESCE(ext.ZJLXMainNetTur, 0)) OVER" in feature
