-- Rebuild prefix tables after loading base tables.
USE `findsl_demo`;

TRUNCATE TABLE `dwd_stock_money_flow_prefix`;
INSERT INTO `dwd_stock_money_flow_prefix`
SELECT
  `ts_code`,
  `trade_date`,
  ROW_NUMBER() OVER (PARTITION BY `ts_code` ORDER BY `trade_date`) AS `row_no`,
  SUM(`main_net_inflow`) OVER (PARTITION BY `ts_code` ORDER BY `trade_date` ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS `main_net_inflow_prefix`
FROM `dwd_stock_money_flow`;

TRUNCATE TABLE `dwd_stock_daily_quote_prefix`;
INSERT INTO `dwd_stock_daily_quote_prefix`
SELECT
  `ts_code`,
  `trade_date`,
  ROW_NUMBER() OVER (PARTITION BY `ts_code` ORDER BY `trade_date`) AS `row_no`,
  SUM(`volume`) OVER (PARTITION BY `ts_code` ORDER BY `trade_date` ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS `volume_prefix`
FROM `dwd_stock_daily_quote`;
