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
