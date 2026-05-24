# Prefix-Sum Benchmark Report

## Summary

- Iterations: 20
- Baseline matches reference: True
- Optimized matches reference: True
- Optimized matches baseline: True
- Local SQLite speedup smoke: 1.18x
- Baseline window frame count: 1
- Optimized prefix table references: 4

Local SQLite timing is a smoke/regression signal, not a Doris-scale performance claim.
The plan-level comparison shows whether the compiler replaced rolling window aggregation with prefix lookups.

## DSL

```text
filter(SUM(indicator("volume"), 3) > 300)
```

## Variant Metrics

| Variant | Compile ms | Avg execute ms | P50 execute ms | P95 execute ms | Rows |
|---|---:|---:|---:|---:|---:|
| baseline_window | 0.455 | 0.032 | 0.029 | 0.036 | 7 |
| optimized_prefix_sum | 0.441 | 0.027 | 0.022 | 0.046 | 7 |

## Generated SQL

### baseline_window

```sql
SELECT * FROM (SELECT base_features.*, SUM(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE __win_1 > 300
```

Trace:
- rewrite SUM() into SUM window feature __win_1
- materialize numeric window features before filtering
- rewrite filter predicate into outer WHERE over materialized features

Explain:
- `PREFIX_SUM` skipped: Prefix-sum optimizer is disabled
- `WINDOW_FEATURE` applied: Rewrite SUM() into SUM window feature
- `FEATURE_LAYER` applied: Materialize numeric features before filtering
- `FILTER_OUTER_WHERE` applied: Rewrite filter predicate into outer WHERE over materialized features
- `DORIS_SQL_VALIDATION` applied: Validate generated SQL against Doris-safe query shape

### optimized_prefix_sum

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
