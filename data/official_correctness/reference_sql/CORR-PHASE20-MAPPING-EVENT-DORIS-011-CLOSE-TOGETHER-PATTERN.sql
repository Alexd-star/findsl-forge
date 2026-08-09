SELECT mktcode,tgtcode,bizdate FROM `newzl`.`hsj_stock_hq_basic_technical` WHERE bizdate='2026-04-14' AND ABS(ma5-ma20)/NULLIF(GREATEST(ABS(ma5),ABS(ma20)),0)<=0.03;
