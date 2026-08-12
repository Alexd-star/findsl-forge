SELECT b.mktcode,b.tgtcode,b.bizdate FROM newzl.hsj_stock_hq_basic b WHERE b.bizdate=(SELECT MAX(a.bizdate) FROM newzl.hsj_stock_hq_basic a) AND ABS(b.volume-b.volume)*1.0/NULLIF(ABS(b.volume),0)=0;
