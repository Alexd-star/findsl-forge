SELECT b.mktcode,b.tgtcode,b.bizdate FROM `newzl`.`hsj_stock_hq_basic` AS b WHERE b.bizdate='2026-04-14' AND NOT (b.mktcode=0 AND (LEFT(b.tgtcode,3) IN ('300','301')));
