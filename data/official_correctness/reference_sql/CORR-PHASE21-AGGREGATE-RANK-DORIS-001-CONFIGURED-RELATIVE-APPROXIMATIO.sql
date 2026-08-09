SELECT mktcode,tgtcode,bizdate FROM `newzl`.`hsj_stock_hq_basic` WHERE bizdate='2026-04-14' AND ABS(lastPx/10000.0-10)<=GREATEST(0.01,0.01*GREATEST(ABS(lastPx/10000.0),ABS(10)));
