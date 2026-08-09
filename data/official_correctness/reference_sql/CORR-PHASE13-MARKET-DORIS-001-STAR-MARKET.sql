SELECT b.mktcode,b.tgtcode,b.bizdate FROM `newzl`.`hsj_stock_hq_basic` AS b WHERE b.bizdate='2026-04-14' AND b.volume>100 AND b.mktcode=1 AND b.tgtcode>='688000' AND b.tgtcode<='688999';
