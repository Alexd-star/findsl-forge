# 官方漏斗差量 Doris 执行审计

- Git HEAD：`cdb6729d937f511c35c5df4fc39d3a8b2189a064`
- 状态：`PASS`
- 真实执行通过：`3/3`
- 每条重复执行：`5` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 1870 | set_intersect | 0 | 45.854 | 547.671 | PASS | PASS |
| 4741 | composite_grouped_aggregate | 0 | 54.954 | 252.385 | PASS | PASS |
| 5742 | composite_grouped_aggregate | 786 | 69.993 | 1631.779 | PASS | PASS |
