-- Official Topic 19 Doris smoke queries.

SELECT COUNT(*) AS code_info_rows FROM newzl.hsj_stock_code_info;
SELECT COUNT(*) AS hq_basic_rows FROM newzl.hsj_stock_hq_basic;
SELECT COUNT(*) AS hq_ext_rows FROM newzl.hsj_stock_hq_ext;

SELECT MIN(bizdate) AS first_basic_date, MAX(bizdate) AS last_basic_date
FROM newzl.hsj_stock_hq_basic;

SELECT MIN(bizdate) AS first_ext_date, MAX(bizdate) AS last_ext_date
FROM newzl.hsj_stock_hq_ext;

SELECT
  COUNT(*) AS joined_rows,
  SUM(CASE WHEN code.name IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_name
FROM newzl.hsj_stock_hq_basic AS base
LEFT JOIN newzl.hsj_stock_code_info AS code
  ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode
WHERE base.bizdate = DATE '2026-04-14';

EXPLAIN
SELECT base.mktcode, base.tgtcode, base.bizdate, code.name
FROM newzl.hsj_stock_hq_basic AS base
LEFT JOIN newzl.hsj_stock_code_info AS code
  ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode
WHERE base.volume > 1000
  AND base.mktcode IN (0)
  AND base.bizdate = DATE '2026-04-14';

EXPLAIN
SELECT *
FROM (
  SELECT base.mktcode, base.tgtcode, base.bizdate, code.name,
         ROW_NUMBER() OVER (
           PARTITION BY base.bizdate
           ORDER BY base.volume DESC, base.tgtcode ASC
         ) AS rank_no
  FROM newzl.hsj_stock_hq_basic AS base
  LEFT JOIN newzl.hsj_stock_code_info AS code
    ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode
  WHERE base.mktcode IN (1)
    AND base.bizdate = DATE '2026-04-14'
) AS ranked
WHERE rank_no <= 10;

EXPLAIN
SELECT base.mktcode, base.tgtcode, base.bizdate, code.name
FROM newzl.hsj_stock_hq_basic AS base
LEFT JOIN newzl.hsj_stock_hq_ext AS ext
  ON ext.mktcode = base.mktcode
 AND ext.tgtcode = base.tgtcode
 AND ext.bizdate = base.bizdate
LEFT JOIN newzl.hsj_stock_code_info AS code
  ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode
WHERE ext.ZJLXMainNetTur > 50000000
  AND base.bizdate = DATE '2026-04-14';
