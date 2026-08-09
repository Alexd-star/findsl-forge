SELECT b.mktcode,b.tgtcode,b.bizdate FROM `newzl`.`hsj_stock_hq_basic` AS b WHERE b.bizdate='2026-04-14' AND b.mktcode=1 AND (LEFT(b.tgtcode,3) IN ('600','601','603','605'));
