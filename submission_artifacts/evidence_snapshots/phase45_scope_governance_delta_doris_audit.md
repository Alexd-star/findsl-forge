# 官方漏斗差量 Doris 执行审计

- Git HEAD：`0a9307b44bfdbb6bd77d338b4178a7fb51338d17`
- 状态：`PASS`
- 真实执行通过：`18/18`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 121 | direct_column | 5 | 47.457 | 206.063 | PASS | PASS |
| 223 | set_intersect | 0 | 52.191 | 666.143 | PASS | PASS |
| 318 | direct_column | 0 | 39.888 | 88.288 | PASS | PASS |
| 463 | stable_key_join | 41 | 49.418 | 741.115 | PASS | PASS |
| 512 | direct_column | 534 | 68.834 | 157.343 | PASS | PASS |
| 518 | direct_column | 15 | 41.834 | 127.773 | PASS | PASS |
| 523 | controlled_expression | 0 | 49.941 | 135.990 | PASS | PASS |
| 536 | direct_column | 23 | 58.433 | 127.593 | PASS | PASS |
| 720 | direct_column | 0 | 61.325 | 142.365 | PASS | PASS |
| 803 | direct_column | 1 | 49.064 | 371.774 | PASS | PASS |
| 1296 | composite_grouped_aggregate | 2498 | 51.433 | 375.707 | PASS | PASS |
| 1404 | temporal_grouped_aggregate | 2 | 53.340 | 205.280 | PASS | PASS |
| 1415 | temporal_cross_scope_scalar | 0 | 46.355 | 321.074 | PASS | PASS |
| 1441 | limit_stage_rank | 0 | 46.669 | 214.142 | PASS | PASS |
| 1486 | crossing_window | 0 | 46.971 | 107.855 | PASS | PASS |
| 3378 | set_intersect | 107 | 51.010 | 690.921 | PASS | PASS |
| 3781 | event_candidate_intersect | 3 | 45.791 | 533.933 | PASS | PASS |
| 4260 | controlled_expression | 3216 | 99.967 | 105.243 | PASS | PASS |
