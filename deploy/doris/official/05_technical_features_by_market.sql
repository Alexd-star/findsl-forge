-- Populate hsj_stock_hq_basic_technical for one market-code and tgtcode-hash shard.
-- scripts/prepare_official_doris_evidence.ps1 replaces __MARKET_CODE__,
-- __BUCKET_ID__, and __BUCKET_COUNT__ to keep each single-node INSERT bounded.

INSERT INTO newzl.hsj_stock_hq_basic_technical
SELECT
  w.mktcode,
  w.tgtcode,
  w.bizdate,
  w.open_price,
  w.high_price,
  w.low_price,
  w.close_price,
  w.previous_close_price,
  w.pressure_price,
  w.support_price,
  w.rise_pct,
  w.ma3,
  w.ma5,
  w.ma10,
  w.ma20,
  w.ma30,
  w.ma60,
  w.ma120,
  w.ma200,
  w.ma250,
  w.volume_avg_5,
  w.volume_avg_10,
  w.volume_avg_20,
  w.volume_avg_30,
  w.volume_avg_60,
  CASE WHEN w.close_price > w.open_price THEN TRUE ELSE FALSE END AS yang_line,
  CASE WHEN w.close_price < w.open_price THEN TRUE ELSE FALSE END AS yin_line,
  CASE
    WHEN w.high_price > w.low_price
     AND ABS(w.close_price - w.open_price) <= (w.high_price - w.low_price) * 0.1
    THEN TRUE ELSE FALSE
  END AS doji,
  CASE WHEN w.volume > w.volume_avg_5 * 1.5 THEN TRUE ELSE FALSE END AS volume_breakout,
  CASE WHEN w.ma5 > w.ma10 AND w.ma10 > w.ma20 AND w.ma20 > w.ma60 THEN TRUE ELSE FALSE END AS ma_bullish,
  CASE WHEN w.ma5 < w.ma10 AND w.ma10 < w.ma20 AND w.ma20 < w.ma60 THEN TRUE ELSE FALSE END AS ma_bearish,
  CASE WHEN w.close_price > w.ma5 AND w.ma5 >= w.ma10 AND w.rise_pct > 0 THEN TRUE ELSE FALSE END AS uptrend,
  CASE
    WHEN w.pressure_price IS NOT NULL
     AND w.previous_close_price IS NOT NULL
     AND w.previous_close_price <= w.pressure_price
     AND w.close_price > w.pressure_price
    THEN TRUE ELSE FALSE
  END AS cross_above_pressure,
  CASE
    WHEN w.support_price IS NOT NULL
     AND w.previous_close_price IS NOT NULL
     AND w.previous_close_price >= w.support_price
     AND w.close_price < w.support_price
    THEN TRUE ELSE FALSE
  END AS cross_down_support
FROM (
  SELECT
    base.mktcode,
    base.tgtcode,
    base.bizdate,
    base.volume,
    base.openPx / 10000.0 AS open_price,
    base.highPx / 10000.0 AS high_price,
    base.lowPx / 10000.0 AS low_price,
    base.closePx / 10000.0 AS close_price,
    p1.close_px / 10000.0 AS previous_close_price,
    base.pressure / 10000.0 AS pressure_price,
    base.support / 10000.0 AS support_price,
    (base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0) AS rise_pct,
    ((p.close_prefix - COALESCE(p3.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p3.close_count_prefix, 0), 0)) / 10000.0 AS ma3,
    ((p.close_prefix - COALESCE(p5.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p5.close_count_prefix, 0), 0)) / 10000.0 AS ma5,
    ((p.close_prefix - COALESCE(p10.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p10.close_count_prefix, 0), 0)) / 10000.0 AS ma10,
    ((p.close_prefix - COALESCE(p20.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p20.close_count_prefix, 0), 0)) / 10000.0 AS ma20,
    ((p.close_prefix - COALESCE(p30.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p30.close_count_prefix, 0), 0)) / 10000.0 AS ma30,
    ((p.close_prefix - COALESCE(p60.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p60.close_count_prefix, 0), 0)) / 10000.0 AS ma60,
    ((p.close_prefix - COALESCE(p120.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p120.close_count_prefix, 0), 0)) / 10000.0 AS ma120,
    ((p.close_prefix - COALESCE(p200.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p200.close_count_prefix, 0), 0)) / 10000.0 AS ma200,
    ((p.close_prefix - COALESCE(p250.close_prefix, 0)) * 1.0
      / NULLIF(p.close_count_prefix - COALESCE(p250.close_count_prefix, 0), 0)) / 10000.0 AS ma250,
    (p.volume_prefix - COALESCE(p5.volume_prefix, 0)) * 1.0
      / NULLIF(p.volume_count_prefix - COALESCE(p5.volume_count_prefix, 0), 0) AS volume_avg_5,
    (p.volume_prefix - COALESCE(p10.volume_prefix, 0)) * 1.0
      / NULLIF(p.volume_count_prefix - COALESCE(p10.volume_count_prefix, 0), 0) AS volume_avg_10,
    (p.volume_prefix - COALESCE(p20.volume_prefix, 0)) * 1.0
      / NULLIF(p.volume_count_prefix - COALESCE(p20.volume_count_prefix, 0), 0) AS volume_avg_20,
    (p.volume_prefix - COALESCE(p30.volume_prefix, 0)) * 1.0
      / NULLIF(p.volume_count_prefix - COALESCE(p30.volume_count_prefix, 0), 0) AS volume_avg_30,
    (p.volume_prefix - COALESCE(p60.volume_prefix, 0)) * 1.0
      / NULLIF(p.volume_count_prefix - COALESCE(p60.volume_count_prefix, 0), 0) AS volume_avg_60
  FROM newzl.hsj_stock_hq_basic AS base
  JOIN newzl.hsj_stock_hq_basic_prefix AS p
    ON p.mktcode = base.mktcode
   AND p.tgtcode = base.tgtcode
   AND p.bizdate = base.bizdate
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p1
    ON p1.mktcode = p.mktcode AND p1.tgtcode = p.tgtcode AND p1.row_no = p.row_no - 1
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p3
    ON p3.mktcode = p.mktcode AND p3.tgtcode = p.tgtcode AND p3.row_no = p.row_no - 3
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p5
    ON p5.mktcode = p.mktcode AND p5.tgtcode = p.tgtcode AND p5.row_no = p.row_no - 5
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p10
    ON p10.mktcode = p.mktcode AND p10.tgtcode = p.tgtcode AND p10.row_no = p.row_no - 10
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p20
    ON p20.mktcode = p.mktcode AND p20.tgtcode = p.tgtcode AND p20.row_no = p.row_no - 20
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p30
    ON p30.mktcode = p.mktcode AND p30.tgtcode = p.tgtcode AND p30.row_no = p.row_no - 30
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p60
    ON p60.mktcode = p.mktcode AND p60.tgtcode = p.tgtcode AND p60.row_no = p.row_no - 60
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p120
    ON p120.mktcode = p.mktcode AND p120.tgtcode = p.tgtcode AND p120.row_no = p.row_no - 120
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p200
    ON p200.mktcode = p.mktcode AND p200.tgtcode = p.tgtcode AND p200.row_no = p.row_no - 200
  LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p250
    ON p250.mktcode = p.mktcode AND p250.tgtcode = p.tgtcode AND p250.row_no = p.row_no - 250
  WHERE base.mktcode = __MARKET_CODE__
    AND MOD(CAST(base.tgtcode AS BIGINT), __BUCKET_COUNT__) = __BUCKET_ID__
) AS w;
