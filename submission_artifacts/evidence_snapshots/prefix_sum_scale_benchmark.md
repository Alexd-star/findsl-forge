# Prefix-Sum Scale Benchmark

## Dataset

- Data directory: `data\generated\scale`
- Stock count: 300
- Day count: 260
- Rows per base table: 78000
- Seed: 2026
- Start date: 2025-01-01

## Query

```text
filter(SUM(indicator("volume"), 120) > 420000)
```

## Correctness Gates

- Baseline matches Pandas reference: True
- Optimized matches Pandas reference: True
- Optimized matches baseline: True

## Performance Signals

- Iterations: 5
- Local SQLite speedup smoke: 1.40x
- Baseline avg execute ms: 288.766
- Optimized avg execute ms: 206.315
- Baseline P95 execute ms: 351.196
- Optimized P95 execute ms: 212.398
- Baseline window frame count: 1
- Optimized prefix table references: 4
- Long-window feature-access reduction estimate: 60.0x

Local SQLite timing is a smoke/regression and plan-shape signal. The reduction estimate compares a window-length rolling scan with two prefix-table lookups per row; final 10x production claims must be backed by Doris EXPLAIN and cluster latency.

## Variant Metrics

| Variant | Compile ms | Avg execute ms | P50 execute ms | P95 execute ms | Rows |
|---|---:|---:|---:|---:|---:|
| baseline_window | 0.948 | 288.766 | 304.649 | 351.196 | 52685 |
| optimized_prefix_sum | 0.503 | 206.315 | 206.643 | 212.398 | 52685 |

## Optimizer Explain

### baseline_window
- `PREFIX_SUM` skipped: Prefix-sum optimizer is disabled
- `WINDOW_FEATURE` applied: Rewrite SUM() into SUM window feature
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### optimized_prefix_sum
- `PREFIX_SUM` applied: Rewrite rolling SUM into prefix table subtraction
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

## Generated SQL

### baseline_window

```sql
SELECT * FROM (SELECT base_features.*, SUM(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE __win_1 > 420000
```

### optimized_prefix_sum

```sql
SELECT * FROM (SELECT base_features.*, (__pref_curr_1.volume_prefix - COALESCE(__pref_prev_1.volume_prefix, 0)) AS __psum_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_curr_1 ON __pref_curr_1.ts_code = base_features.ts_code AND __pref_curr_1.trade_date = base_features.trade_date LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_prev_1 ON __pref_prev_1.ts_code = __pref_curr_1.ts_code AND __pref_prev_1.row_no = __pref_curr_1.row_no - 120) numeric_features_1 WHERE __psum_1 > 420000
```