-- Official Topic 19 feature tables for long-window acceleration.
-- Rebuild after loading or refreshing official CSV tables.

CREATE TABLE IF NOT EXISTS newzl.hsj_stock_hq_basic_prefix (
  mktcode INTEGER NOT NULL,
  tgtcode VARCHAR(16) NOT NULL,
  bizdate DATE NOT NULL,
  row_no BIGINT NOT NULL,
  volume_prefix BIGINT,
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

INSERT INTO newzl.hsj_stock_hq_basic_prefix
SELECT
  base.mktcode,
  base.tgtcode,
  base.bizdate,
  ROW_NUMBER() OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate) AS row_no,
  SUM(base.volume) OVER (
    PARTITION BY base.mktcode, base.tgtcode
    ORDER BY base.bizdate
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS volume_prefix,
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
FROM newzl.hsj_stock_hq_basic AS base;

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
  ma5 DOUBLE,
  ma10 DOUBLE,
  ma20 DOUBLE,
  ma60 DOUBLE,
  volume_avg_5 DOUBLE,
  volume_avg_20 DOUBLE,
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
  w.ma5,
  w.ma10,
  w.ma20,
  w.ma60,
  w.volume_avg_5,
  w.volume_avg_20,
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
    LAG(base.closePx / 10000.0) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
    ) AS previous_close_price,
    base.pressure / 10000.0 AS pressure_price,
    base.support / 10000.0 AS support_price,
    (base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0) AS rise_pct,
    AVG(base.closePx / 10000.0) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS ma5,
    AVG(base.closePx / 10000.0) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
    ) AS ma10,
    AVG(base.closePx / 10000.0) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS ma20,
    AVG(base.closePx / 10000.0) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
    ) AS ma60,
    AVG(base.volume) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS volume_avg_5,
    AVG(base.volume) OVER (
      PARTITION BY base.mktcode, base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS volume_avg_20
  FROM newzl.hsj_stock_hq_basic AS base
) AS w;
