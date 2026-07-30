-- Narrow serving table for fixed rolling features on the official 20-year data.
-- Monthly AUTO PARTITION keeps exact-date screens on one partition while the
-- source prefix table remains the complete, auditable historical calculation.

DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_rollup;

CREATE TABLE newzl.hsj_stock_hq_basic_rollup (
  bizdate DATE NOT NULL,
  mktcode INTEGER NOT NULL,
  tgtcode VARCHAR(16) NOT NULL,
  volume_sum_5 BIGINT,
  volume_sum_20 BIGINT,
  turnover_sum_20 BIGINT
)
UNIQUE KEY(bizdate, mktcode, tgtcode)
AUTO PARTITION BY RANGE (date_trunc(bizdate, 'month')) ()
DISTRIBUTED BY HASH(mktcode, tgtcode) BUCKETS 16
PROPERTIES (
  "replication_num" = "1",
  "compression" = "LZ4",
  "enable_unique_key_merge_on_write" = "true"
);

INSERT INTO newzl.hsj_stock_hq_basic_rollup (
  bizdate,
  mktcode,
  tgtcode,
  volume_sum_5,
  volume_sum_20,
  turnover_sum_20
)
SELECT
  bizdate,
  mktcode,
  tgtcode,
  volume_sum_5,
  volume_sum_20,
  turnover_sum_20
FROM newzl.hsj_stock_hq_basic_prefix;
