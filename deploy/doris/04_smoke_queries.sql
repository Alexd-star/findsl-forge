-- Smoke queries generated from the same DSL with optimizer on/off.
USE `findsl_demo`;

-- Optimized prefix-sum SQL
SELECT * FROM (SELECT base_features.*, (__pref_curr_1.volume_prefix - COALESCE(__pref_prev_1.volume_prefix, 0)) AS __psum_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_curr_1 ON __pref_curr_1.ts_code = base_features.ts_code AND __pref_curr_1.trade_date = base_features.trade_date LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_prev_1 ON __pref_prev_1.ts_code = __pref_curr_1.ts_code AND __pref_prev_1.row_no = __pref_curr_1.row_no - 3) numeric_features_1 WHERE __psum_1 > 300;

-- Baseline window SQL
SELECT * FROM (SELECT base_features.*, SUM(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE __win_1 > 300;
