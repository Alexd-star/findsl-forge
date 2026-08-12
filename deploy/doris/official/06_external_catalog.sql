CREATE DATABASE IF NOT EXISTS findsl_ext;

CREATE TABLE IF NOT EXISTS findsl_ext.scope_membership (
  snapshot_id VARCHAR(128) NOT NULL,
  scope_code VARCHAR(64) NOT NULL,
  mktcode INT NOT NULL,
  tgtcode VARCHAR(32) NOT NULL,
  scope_type VARCHAR(32) NOT NULL,
  scope_name VARCHAR(256) NOT NULL,
  effective_from DATE NULL,
  effective_to DATE NULL,
  weight DOUBLE NULL
)
DUPLICATE KEY(snapshot_id, scope_code, mktcode, tgtcode)
DISTRIBUTED BY HASH(tgtcode) BUCKETS 16
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS findsl_ext.industry_membership (
  snapshot_id VARCHAR(128) NOT NULL,
  classification_system VARCHAR(128) NOT NULL,
  industry_code VARCHAR(64) NOT NULL,
  mktcode INT NOT NULL,
  tgtcode VARCHAR(32) NOT NULL,
  industry_level VARCHAR(32) NOT NULL,
  industry_name VARCHAR(256) NOT NULL,
  effective_from DATE NULL,
  effective_to DATE NULL
)
DUPLICATE KEY(snapshot_id, classification_system, industry_code, mktcode, tgtcode)
DISTRIBUTED BY HASH(tgtcode) BUCKETS 16
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS findsl_ext.instrument_rule (
  snapshot_id VARCHAR(128) NOT NULL,
  mktcode INT NOT NULL,
  tgtcode VARCHAR(32) NOT NULL,
  instrument_type VARCHAR(64) NOT NULL,
  t0_eligible BOOLEAN NOT NULL,
  effective_from DATE NULL,
  effective_to DATE NULL,
  rule_source VARCHAR(512) NOT NULL
)
DUPLICATE KEY(snapshot_id, mktcode, tgtcode)
DISTRIBUTED BY HASH(tgtcode) BUCKETS 16
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS findsl_ext.index_quote (
  snapshot_id VARCHAR(128) NOT NULL,
  index_code VARCHAR(32) NOT NULL,
  bizdate DATE NOT NULL,
  open DOUBLE NULL,
  high DOUBLE NULL,
  low DOUBLE NULL,
  close DOUBLE NULL,
  volume BIGINT NULL,
  pct_change DOUBLE NULL,
  source VARCHAR(128) NOT NULL
)
DUPLICATE KEY(snapshot_id, index_code, bizdate)
DISTRIBUTED BY HASH(index_code) BUCKETS 8
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS findsl_ext.index_quote_security_shape (
  mktcode INT NOT NULL,
  tgtcode VARCHAR(32) NOT NULL,
  bizdate DATE NOT NULL,
  snapshot_id VARCHAR(128) NOT NULL,
  open DOUBLE NULL,
  high DOUBLE NULL,
  low DOUBLE NULL,
  close DOUBLE NULL,
  volume BIGINT NULL,
  pct_change DOUBLE NULL
)
DUPLICATE KEY(mktcode, tgtcode, bizdate)
DISTRIBUTED BY HASH(tgtcode) BUCKETS 8
PROPERTIES ("replication_num" = "1");
