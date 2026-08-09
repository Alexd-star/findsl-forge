SELECT mktcode,tgtcode,bizdate FROM `newzl`.`hsj_stock_hq_ext` WHERE bizdate='2026-04-14' AND (COALESCE(lmtUpNum,0)>0 OR COALESCE(boardBreaks,0)>0);
