-- Official Topic 19 feature tables for long-window acceleration.
-- Rebuild after loading or refreshing official CSV tables.

CREATE TABLE IF NOT EXISTS newzl.hsj_stock_hq_basic_prefix (
  mktcode INTEGER NOT NULL,
  tgtcode VARCHAR(16) NOT NULL,
  bizdate DATE NOT NULL,
  row_no BIGINT NOT NULL,
  close_px BIGINT,
  close_prefix BIGINT,
  close_count_prefix BIGINT,
  volume_prefix BIGINT,
  volume_count_prefix BIGINT,
  turnover_prefix BIGINT,
  volume_sum_5 BIGINT,
  volume_sum_20 BIGINT,
  turnover_sum_20 BIGINT
)
UNIQUE KEY(mktcode, tgtcode, bizdate)
DISTRIBUTED BY HASH(mktcode, tgtcode) BUCKETS 16
PROPERTIES (
  "replication_num" = "1",
  "compression" = "LZ4",
  "enable_unique_key_merge_on_write" = "true"
);

TRUNCATE TABLE newzl.hsj_stock_hq_basic_prefix;

-- Build by official market code to keep single-node evidence memory stable.
INSERT INTO newzl.hsj_stock_hq_basic_prefix
SELECT
  base.mktcode,
  base.tgtcode,
  base.bizdate,
  ROW_NUMBER() OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate) AS row_no,
  base.closePx AS close_px,
  SUM(COALESCE(base.closePx, 0)) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS close_prefix,
  SUM(CASE WHEN base.closePx IS NULL THEN 0 ELSE 1 END) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS close_count_prefix,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_prefix,
  SUM(CASE WHEN base.volume IS NULL THEN 0 ELSE 1 END) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_count_prefix,
  SUM(base.turnover) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS turnover_prefix,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
  ) AS volume_sum_5,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS volume_sum_20,
  SUM(base.turnover) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS turnover_sum_20
FROM newzl.hsj_stock_hq_basic AS base
WHERE base.mktcode = 0;

INSERT INTO newzl.hsj_stock_hq_basic_prefix
SELECT
  base.mktcode,
  base.tgtcode,
  base.bizdate,
  ROW_NUMBER() OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate) AS row_no,
  base.closePx AS close_px,
  SUM(COALESCE(base.closePx, 0)) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS close_prefix,
  SUM(CASE WHEN base.closePx IS NULL THEN 0 ELSE 1 END) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS close_count_prefix,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_prefix,
  SUM(CASE WHEN base.volume IS NULL THEN 0 ELSE 1 END) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_count_prefix,
  SUM(base.turnover) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS turnover_prefix,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
  ) AS volume_sum_5,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS volume_sum_20,
  SUM(base.turnover) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS turnover_sum_20
FROM newzl.hsj_stock_hq_basic AS base
WHERE base.mktcode = 1;

INSERT INTO newzl.hsj_stock_hq_basic_prefix
SELECT
  base.mktcode,
  base.tgtcode,
  base.bizdate,
  ROW_NUMBER() OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate) AS row_no,
  base.closePx AS close_px,
  SUM(COALESCE(base.closePx, 0)) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS close_prefix,
  SUM(CASE WHEN base.closePx IS NULL THEN 0 ELSE 1 END) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS close_count_prefix,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_prefix,
  SUM(CASE WHEN base.volume IS NULL THEN 0 ELSE 1 END) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_count_prefix,
  SUM(base.turnover) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS turnover_prefix,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
  ) AS volume_sum_5,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS volume_sum_20,
  SUM(base.turnover) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS turnover_sum_20
FROM newzl.hsj_stock_hq_basic AS base
WHERE base.mktcode = 103;

CREATE TABLE IF NOT EXISTS newzl.hsj_stock_hq_ext_prefix (
  mktcode INTEGER NOT NULL,
  tgtcode VARCHAR(16) NOT NULL,
  bizdate DATE NOT NULL,
  row_no BIGINT NOT NULL,
  main_net_tur_prefix BIGINT,
  main_net_tur_sum_5 BIGINT,
  main_net_tur_sum_20 BIGINT
)
UNIQUE KEY(mktcode, tgtcode, bizdate)
DISTRIBUTED BY HASH(mktcode, tgtcode) BUCKETS 16
PROPERTIES (
  "replication_num" = "1",
  "compression" = "LZ4",
  "enable_unique_key_merge_on_write" = "true"
);

TRUNCATE TABLE newzl.hsj_stock_hq_ext_prefix;

INSERT INTO newzl.hsj_stock_hq_ext_prefix
SELECT
  base.mktcode,
  base.tgtcode,
  base.bizdate,
  ROW_NUMBER() OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate) AS row_no,
  SUM(COALESCE(ext.ZJLXMainNetTur, 0)) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS main_net_tur_prefix,
  SUM(COALESCE(ext.ZJLXMainNetTur, 0)) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
  ) AS main_net_tur_sum_5,
  SUM(COALESCE(ext.ZJLXMainNetTur, 0)) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS main_net_tur_sum_20
FROM newzl.hsj_stock_hq_basic AS base
LEFT JOIN newzl.hsj_stock_hq_ext AS ext
  ON ext.mktcode = base.mktcode
 AND ext.tgtcode = base.tgtcode
 AND ext.bizdate = base.bizdate;

CREATE TABLE IF NOT EXISTS newzl.hsj_stock_hq_basic_technical (
  mktcode INTEGER NOT NULL,
  tgtcode VARCHAR(16) NOT NULL,
  bizdate DATE NOT NULL,
  open_price DOUBLE,
  high_price DOUBLE,
  low_price DOUBLE,
  close_price DOUBLE,
  previous_close_price DOUBLE,
  pressure_price DOUBLE,
  support_price DOUBLE,
  rise_pct DOUBLE,
  ma3 DOUBLE,
  ma5 DOUBLE,
  ma10 DOUBLE,
  ma20 DOUBLE,
  ma30 DOUBLE,
  ma60 DOUBLE,
  ma120 DOUBLE,
  ma200 DOUBLE,
  ma250 DOUBLE,
  volume_avg_5 DOUBLE,
  volume_avg_10 DOUBLE,
  volume_avg_20 DOUBLE,
  volume_avg_30 DOUBLE,
  volume_avg_60 DOUBLE,
  yang_line BOOLEAN,
  yin_line BOOLEAN,
  doji BOOLEAN,
  volume_breakout BOOLEAN,
  ma_bullish BOOLEAN,
  ma_bearish BOOLEAN,
  uptrend BOOLEAN,
  cross_above_pressure BOOLEAN,
  cross_down_support BOOLEAN
)
UNIQUE KEY(mktcode, tgtcode, bizdate)
DISTRIBUTED BY HASH(mktcode, tgtcode) BUCKETS 16
PROPERTIES (
  "replication_num" = "1",
  "compression" = "LZ4",
  "enable_unique_key_merge_on_write" = "true"
);

TRUNCATE TABLE newzl.hsj_stock_hq_basic_technical;

/*
Technical table population is executed from 05_technical_features_by_market.sql
with one market-code shard per INSERT. Keeping this all-market SQL block disabled
documents the full expression shape while avoiding single-node evidence OOM.

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
) AS w;
*/
