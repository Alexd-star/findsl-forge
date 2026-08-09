SELECT b.mktcode,b.tgtcode,b.bizdate FROM `newzl`.`hsj_stock_hq_basic` AS b INNER JOIN `newzl`.`hsj_stock_code_info` AS s ON s.mktcode=b.mktcode AND s.tgtcode=b.tgtcode WHERE s.name='华泰证券';
