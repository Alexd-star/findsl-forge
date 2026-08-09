from pathlib import Path


OFFICIAL_DORIS_DIR = Path("deploy/doris/official")


def test_official_doris_assets_are_present_and_target_real_tables():
    schema = (OFFICIAL_DORIS_DIR / "01_schema.sql").read_text(encoding="utf-8")
    stream_load = (OFFICIAL_DORIS_DIR / "02_stream_load.md").read_text(encoding="utf-8")
    smoke = (OFFICIAL_DORIS_DIR / "03_smoke_queries.sql").read_text(encoding="utf-8")
    feature = (OFFICIAL_DORIS_DIR / "04_feature_tables.sql").read_text(encoding="utf-8")
    technical_feature = (OFFICIAL_DORIS_DIR / "05_technical_features_by_market.sql").read_text(encoding="utf-8")
    official_evidence_script = Path("scripts/prepare_official_doris_evidence.ps1").read_text(encoding="utf-8")
    export_script = Path("scripts/export_submission_artifacts.ps1").read_text(encoding="utf-8")

    assert "CREATE DATABASE IF NOT EXISTS newzl" in schema
    assert "CREATE TABLE IF NOT EXISTS newzl.hsj_stock_hq_basic" in schema
    assert "UNIQUE KEY(mktcode, tgtcode, bizdate)" in schema
    assert "quantRatio INTEGER" in schema
    assert "lastPx BIGINT,\n  preClosePx BIGINT," in schema
    assert "lastPx BIGINT NOT NULL" not in schema
    assert "preClosePx BIGINT NOT NULL" not in schema
    assert "DEFAULT FALSE" not in schema
    assert "stFlag BOOLEAN NOT NULL DEFAULT '0'" in schema
    assert '"enable_unique_key_merge_on_write" = "true"' in schema

    assert "Stream Load" in stream_load
    assert "hsj_stock_code_info.csv" in stream_load
    assert "hsj_stock_hq_basic.csv" in stream_load
    assert "hsj_stock_hq_ext.csv" in stream_load
    assert "strict_mode:true" in stream_load
    assert "_stream_load" in stream_load

    assert "SELECT COUNT(*) AS hq_basic_rows" in smoke
    assert "EXPLAIN" in smoke
    assert "ROW_NUMBER() OVER" in smoke

    assert "hsj_stock_hq_basic_prefix" in feature
    assert "close_prefix BIGINT" in feature
    assert "close_count_prefix BIGINT" in feature
    assert "volume_count_prefix BIGINT" in feature
    assert "WHERE base.mktcode = 0" in feature
    assert "WHERE base.mktcode = 1" in feature
    assert "WHERE base.mktcode = 103" in feature
    assert "SUM(base.volume) OVER" in feature
    assert "hsj_stock_hq_ext_prefix" in feature
    assert "SUM(COALESCE(ext.ZJLXMainNetTur, 0)) OVER" in feature
    assert "hsj_stock_hq_basic_technical" in feature
    assert "ma5 DOUBLE" in feature
    assert "ma30 DOUBLE" in feature
    assert "ma120 DOUBLE" in feature
    assert "ma250 DOUBLE" in feature
    assert "volume_avg_30 DOUBLE" in feature
    assert "volume_avg_60 DOUBLE" in feature
    assert "LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p250" in technical_feature
    assert "__MARKET_CODE__" in technical_feature
    assert "__BUCKET_ID__" in technical_feature
    assert "__BUCKET_COUNT__" in technical_feature
    assert "WHERE base.mktcode = __MARKET_CODE__" in technical_feature
    assert "MOD(CAST(base.tgtcode AS BIGINT), __BUCKET_COUNT__) = __BUCKET_ID__" in technical_feature
    assert "ma_bullish BOOLEAN" in feature
    assert "volume_breakout BOOLEAN" in feature
    assert "doji BOOLEAN" in feature

    assert "prepare_official_doris_evidence" in official_evidence_script
    assert "13650347" in official_evidence_script
    assert "6170822" in official_evidence_script
    assert "strict_mode:true" in official_evidence_script
    assert "NumberFilteredRows" in official_evidence_script
    assert "Get-FileHash" in official_evidence_script
    assert '[int]$StreamLoadPort = 8040' in official_evidence_script
    assert 'http://${StreamLoadHost}:${StreamLoadPort}/api/newzl/${Table}/_stream_load' in official_evidence_script
    assert '"Expect: 100-continue"' in official_evidence_script
    assert "[Path]$EvidenceOutput" not in official_evidence_script
    assert "[System.IO.Path]::ChangeExtension" in official_evidence_script
    assert "$needBaseLoad = -not $SkipStreamLoad" in official_evidence_script
    assert "idempotent row-count match" in official_evidence_script
    assert "Preserving complete official base tables" in official_evidence_script
    assert "Preserving existing feature tables because -SkipFeatureTables was set" in official_evidence_script
    assert "if (-not $SkipFeatureTables) {" in official_evidence_script
    assert "05_technical_features_by_market.sql" in official_evidence_script
    assert "foreach ($marketCode in @(0, 1, 103))" in official_evidence_script
    assert "foreach ($bucketId in 0..($TechnicalBucketCount - 1))" in official_evidence_script
    assert "DROP TABLE IF EXISTS newzl.hsj_stock_hq_ext; DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic;" in official_evidence_script
    assert "Baseline/prefix row-count match: $baselinePrefixRowCountMatch" in official_evidence_script
    assert "Official feature tables available: $featureTablesAvailable" in official_evidence_script
    assert "## Feature Table Row Counts" in official_evidence_script
    assert "hsj_stock_hq_basic_technical" in official_evidence_script
    assert "feature_table_row_counts = $FeatureRows" in official_evidence_script
    assert "baseline_prefix_row_count_match = $baselinePrefixRowCountMatch" in official_evidence_script
    assert "Baseline/prefix row-count mismatch" in official_evidence_script
    assert "WHERE base.bizdate BETWEEN DATE_SUB(DATE '2026-04-14', INTERVAL 80 DAY)" not in official_evidence_script

    assert "official_doris_evidence.md" in export_script
    assert "official_doris_evidence.json" in export_script
    assert "official_slot_coverage.md" in export_script
    assert "official_slot_coverage.json" in export_script
