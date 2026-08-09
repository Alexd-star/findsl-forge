SELECT b.mktcode,b.tgtcode,b.bizdate FROM `newzl`.`hsj_stock_hq_basic` AS b WHERE b.mktcode=1 AND b.bizdate IN ('2026-04-07','2026-04-08','2026-04-09') AND b.volume>100000000;
