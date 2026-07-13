# 官方漏斗差量 Doris 执行审计

- Git HEAD：`2c72d7432ed630a2bedb45853dc09cd5345e2695`
- 状态：`PASS`
- 真实执行通过：`3/3`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 657 | direct_column | 3 | 87.290 | 1045.770 | PASS | PASS |
| 789 | composite_grouped_aggregate | 0 | 125.037 | 1065.360 | PASS | PASS |
| 2413 | grouped_aggregate | 13 | 96.359 | 513.533 | PASS | PASS |
