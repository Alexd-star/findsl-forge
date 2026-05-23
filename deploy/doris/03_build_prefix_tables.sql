-- Rebuild prefix tables after loading base tables.
USE `findsl_demo`;

TRUNCATE TABLE `dwd_stock_money_flow_prefix`;
INSERT INTO `dwd_stock_money_flow_prefix`
SELECT
  base.`ts_code` AS `ts_code`,
  base.`trade_date` AS `trade_date`,
  ROW_NUMBER() OVER (PARTITION BY base.`ts_code` ORDER BY base.`trade_date`) AS `row_no`,
  SUM(src.`main_net_inflow`) OVER (PARTITION BY base.`ts_code` ORDER BY base.`trade_date` ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS `main_net_inflow_prefix`
FROM `dwd_stock_daily_quote` AS base
LEFT JOIN `dwd_stock_money_flow` AS src ON src.`ts_code` = base.`ts_code` AND src.`trade_date` = base.`trade_date`;

TRUNCATE TABLE `dwd_stock_daily_quote_prefix`;
INSERT INTO `dwd_stock_daily_quote_prefix`
SELECT
  `ts_code`,
  `trade_date`,
  ROW_NUMBER() OVER (PARTITION BY `ts_code` ORDER BY `trade_date`) AS `row_no`,
  SUM(`volume`) OVER (PARTITION BY `ts_code` ORDER BY `trade_date` ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS `volume_prefix`,
  SUM(`volume`) OVER (PARTITION BY `ts_code` ORDER BY `trade_date` ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS `volume_sum_120`
FROM `dwd_stock_daily_quote`;
