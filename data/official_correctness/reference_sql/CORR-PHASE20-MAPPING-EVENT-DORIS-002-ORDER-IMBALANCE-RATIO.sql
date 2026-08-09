SELECT mktcode,tgtcode,bizdate FROM `newzl`.`hsj_stock_hq_basic` WHERE bizdate='2026-04-14' AND (commissionBuy-commissionSale)*100.0/NULLIF(commissionBuy+commissionSale,0)>10;
