WITH recent_dates AS (
  SELECT bizdate
  FROM newzl.hsj_stock_hq_basic
  GROUP BY bizdate
  ORDER BY bizdate DESC
  LIMIT 5000
), qualified AS (
  SELECT b.mktcode, b.tgtcode
  FROM newzl.hsj_stock_hq_basic AS b
  WHERE b.bizdate IN (SELECT bizdate FROM recent_dates)
  GROUP BY b.mktcode, b.tgtcode
  HAVING SUM(b.volume) > 10000000
)
SELECT a.mktcode, a.tgtcode, a.bizdate
FROM newzl.hsj_stock_hq_basic AS a
INNER JOIN qualified AS q
  ON q.mktcode = a.mktcode AND q.tgtcode = a.tgtcode
WHERE a.bizdate = (SELECT MAX(bizdate) FROM newzl.hsj_stock_hq_basic);
