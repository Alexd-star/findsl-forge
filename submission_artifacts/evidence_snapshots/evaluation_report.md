# FinDSL Forge Evaluation Report

## Summary

- Total cases: 10
- Passed cases: 10
- Failed cases: 0
- Compile success rate: 100.00%
- Fragment accuracy: 100.00%
- Average compile latency: 0.352 ms
- P50 compile latency: 0.319 ms
- P95 compile latency: 0.664 ms

## Case Details

| Case | Passed | Latency ms | Errors |
|---|---:|---:|---|
| 连续3天主力净流入为正后按换手率排名 | True | 0.768 |  |
| 今日收盘价创250日新高 | True | 0.294 |  |
| 近10日存在放量 | True | 0.347 |  |
| 无引号指标名兼容 | True | 0.238 |  |
| 近3日成交量前缀和加速 | True | 0.343 |  |
| A股每日换手率前50百分比 | True | 0.536 |  |
| 日期区间内收盘价大于10 | True | 0.244 |  |
| 窗口查询日期上界安全裁剪 | True | 0.351 |  |
| 主力净流出负阈值 | True | 0.185 |  |
| 近2日收盘价收益率超过5% | True | 0.219 |  |

## Generated SQL

### 连续3天主力净流入为正后按换手率排名

```sql
WITH stage1 AS (SELECT * FROM (SELECT base_features.*, SUM(CASE WHEN main_net_inflow > 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS __roll_1 FROM (SELECT base.*, mf.main_net_inflow AS main_net_inflow, su.market AS market FROM dwd_stock_daily_quote AS base LEFT JOIN dwd_stock_money_flow AS mf USING (ts_code, trade_date) LEFT JOIN dim_stock_universe AS su USING (ts_code, trade_date)) base_features) rolling_features_1 WHERE (market = 'A' AND __roll_1 = 3)), stage2 AS (SELECT * FROM (SELECT base.*, ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY turnover_rate DESC, ts_code ASC) AS rank_no FROM (SELECT base.ts_code AS ts_code, base.trade_date AS trade_date, base.close AS close, base.turnover_rate AS turnover_rate, base.volume AS volume, base.main_net_inflow AS main_net_inflow, base.market AS market FROM stage1 AS base) AS base WHERE turnover_rate IS NOT NULL) ranked WHERE rank_no <= 100) SELECT * FROM stage2
```

Trace:
- rewrite then() into staged CTE pipeline
- rewrite CONS() into rolling window feature __roll_1
- materialize rolling boolean features after numeric features
- rewrite filter predicate into outer WHERE over materialized features
- project staged relation columns before re-ranking
- project staged relation columns before re-ranking
- rewrite rank() into ROW_NUMBER window
- exclude null rank expressions before applying rank cutoff

Explain:
- `THEN_PIPELINE` applied: Rewrite then() into staged CTE pipeline
- `ROLLING_BOOLEAN` applied: Rewrite CONS() into rolling boolean window feature
- `FEATURE_LAYER` applied: Materialize rolling boolean features after numeric features
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `RELATION_PROJECTION` applied: Project staged relation columns before re-ranking
- `RELATION_PROJECTION` applied: Project staged relation columns before re-ranking
- `RANK_ROW_NUMBER` applied: Rewrite rank() into ROW_NUMBER window
- `RANK_NULL_GUARD` applied: Exclude null rank expressions before applying rank cutoff
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 今日收盘价创250日新高

```sql
SELECT * FROM (SELECT base_features.*, MAX(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 249 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE close >= __win_1
```

Trace:
- rewrite MAX() into MAX window feature __win_1
- materialize numeric window features before filtering
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `WINDOW_FEATURE` applied: Rewrite MAX() into MAX window feature
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 近10日存在放量

```sql
SELECT * FROM (SELECT numeric_features_1.*, MAX(CASE WHEN volume > __win_1 THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS __roll_2 FROM (SELECT base_features.*, AVG(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1) rolling_features_1 WHERE __roll_2 = 1
```

Trace:
- rewrite MA() into AVG window feature __win_1
- rewrite EXIST() into rolling window feature __roll_2
- materialize numeric window features before filtering
- materialize rolling boolean features after numeric features
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `WINDOW_FEATURE` applied: Rewrite MA() into AVG window feature
- `ROLLING_BOOLEAN` applied: Rewrite EXIST() into rolling boolean window feature
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FEATURE_LAYER` applied: Materialize rolling boolean features after numeric features
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 无引号指标名兼容

```sql
SELECT * FROM (SELECT base_features.*, AVG(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE close > __win_1
```

Trace:
- rewrite MA() into AVG window feature __win_1
- materialize numeric window features before filtering
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `WINDOW_FEATURE` applied: Rewrite MA() into AVG window feature
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 近3日成交量前缀和加速

```sql
SELECT * FROM (SELECT base_features.*, (__pref_curr_1.volume_prefix - COALESCE(__pref_prev_1.volume_prefix, 0)) AS __psum_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_curr_1 ON __pref_curr_1.ts_code = base_features.ts_code AND __pref_curr_1.trade_date = base_features.trade_date LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_prev_1 ON __pref_prev_1.ts_code = __pref_curr_1.ts_code AND __pref_prev_1.row_no = __pref_curr_1.row_no - 3) numeric_features_1 WHERE __psum_1 > 300
```

Trace:
- rewrite SUM() on volume into prefix-sum feature __psum_1
- materialize numeric window features before filtering
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `PREFIX_SUM` applied: Rewrite rolling SUM into prefix table subtraction
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### A股每日换手率前50百分比

```sql
WITH stage1 AS (SELECT * FROM (SELECT base.*, su.market AS market FROM dwd_stock_daily_quote AS base LEFT JOIN dim_stock_universe AS su USING (ts_code, trade_date)) base_features WHERE market = 'A'), stage2 AS (SELECT * FROM (SELECT base.*, ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY turnover_rate DESC, ts_code ASC) AS rank_no FROM (SELECT base.*, COUNT(*) OVER (PARTITION BY trade_date) AS __partition_count FROM (SELECT base.ts_code AS ts_code, base.trade_date AS trade_date, base.close AS close, base.turnover_rate AS turnover_rate, base.volume AS volume, base.market AS market FROM stage1 AS base) AS base) base WHERE turnover_rate IS NOT NULL) ranked WHERE rank_no <= CAST(((__partition_count * 50) + 99.999999) / 100.0 AS INTEGER)) SELECT * FROM stage2
```

Trace:
- rewrite then() into staged CTE pipeline
- rewrite filter predicate into outer WHERE over materialized features
- project staged relation columns before re-ranking
- project staged relation columns before re-ranking
- rewrite rank() into ROW_NUMBER window
- exclude null rank expressions before applying rank cutoff

Explain:
- `THEN_PIPELINE` applied: Rewrite then() into staged CTE pipeline
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `RELATION_PROJECTION` applied: Project staged relation columns before re-ranking
- `RELATION_PROJECTION` applied: Project staged relation columns before re-ranking
- `RANK_ROW_NUMBER` applied: Rewrite rank() into ROW_NUMBER window
- `RANK_NULL_GUARD` applied: Exclude null rank expressions before applying rank cutoff
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 日期区间内收盘价大于10

```sql
SELECT * FROM (SELECT base.* FROM dwd_stock_daily_quote AS base WHERE (trade_date >= '2026-01-02' AND trade_date <= '2026-01-04')) base_features WHERE ((trade_date >= '2026-01-02' AND trade_date <= '2026-01-04') AND close > 10)
```

Trace:
- rewrite date_between() into trade_date range predicate
- push safe date range predicate into base scan
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `DATE_RANGE_PUSHDOWN` applied: Rewrite date_between() into trade_date range predicate
- `DATE_RANGE_BASE_PRUNING` applied: Push safe date range predicate into base scan
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 窗口查询日期上界安全裁剪

```sql
SELECT * FROM (SELECT base_features.*, AVG(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base WHERE trade_date <= '2026-01-04') base_features) numeric_features_1 WHERE ((trade_date >= '2026-01-02' AND trade_date <= '2026-01-04') AND close > __win_1)
```

Trace:
- rewrite date_between() into trade_date range predicate
- rewrite MA() into AVG window feature __win_1
- push safe date upper bound into base scan for window context
- materialize numeric window features before filtering
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `DATE_RANGE_PUSHDOWN` applied: Rewrite date_between() into trade_date range predicate
- `WINDOW_FEATURE` applied: Rewrite MA() into AVG window feature
- `DATE_RANGE_WINDOW_PRUNING` applied: Push safe date upper bound into base scan without truncating window history
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 主力净流出负阈值

```sql
SELECT * FROM (SELECT base.*, mf.main_net_inflow AS main_net_inflow FROM dwd_stock_daily_quote AS base LEFT JOIN dwd_stock_money_flow AS mf USING (ts_code, trade_date)) base_features WHERE main_net_inflow < -1.5
```

Trace:
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### 近2日收盘价收益率超过5%

```sql
SELECT * FROM (SELECT base_features.*, ((close) / NULLIF(LAG(close, 2) OVER (PARTITION BY ts_code ORDER BY trade_date), 0) - 1) AS __ret_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE __ret_1 > 0.05
```

Trace:
- rewrite RET() into lag return-rate feature __ret_1
- materialize numeric window features before filtering
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `RETURN_RATE` applied: Rewrite RET() into LAG-based return-rate feature
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape
