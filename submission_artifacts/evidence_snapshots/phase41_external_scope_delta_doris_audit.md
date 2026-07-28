# 官方漏斗差量 Doris 执行审计

- Git HEAD：`ab69ff6b0a68695ea55497c5e443a372a3c2f4e4`
- 状态：`PASS`
- 真实执行通过：`15/15`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 120 | controlled_expression | 32 | 54.162 | 526.735 | PASS | PASS |
| 401 | direct_column | 3 | 61.496 | 293.863 | PASS | PASS |
| 405 | direct_column | 223 | 58.085 | 198.362 | PASS | PASS |
| 443 | direct_column | 90 | 55.950 | 215.249 | PASS | PASS |
| 508 | direct_column | 3 | 49.854 | 243.948 | PASS | PASS |
| 521 | controlled_expression | 1 | 51.061 | 134.700 | PASS | PASS |
| 538 | direct_column | 8 | 51.326 | 177.225 | PASS | PASS |
| 542 | controlled_expression | 0 | 63.390 | 148.259 | PASS | PASS |
| 759 | direct_column | 140 | 64.382 | 282.909 | PASS | PASS |
| 1224 | set_union | 877 | 62.857 | 388.966 | PASS | PASS |
| 1406 | temporal_grouped_aggregate | 11 | 47.730 | 247.027 | PASS | PASS |
| 1544 | stable_key_join | 37 | 79.750 | 1999.431 | PASS | PASS |
| 1639 | crossing_window | 0 | 56.186 | 192.804 | PASS | PASS |
| 3106 | controlled_expression | 0 | 66.179 | 148.260 | PASS | PASS |
| 4957 | set_intersect | 0 | 64.112 | 581.159 | PASS | PASS |
