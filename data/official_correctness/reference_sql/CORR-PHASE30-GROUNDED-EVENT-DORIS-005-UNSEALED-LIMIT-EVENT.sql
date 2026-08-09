SELECT b.mktcode,b.tgtcode,b.bizdate FROM `newzl`.`hsj_stock_hq_basic` b WHERE b.bizdate='2026-02-25' AND b.upSealPx>0 AND b.highPx>=b.upSealPx AND b.limitFlag<>1;
