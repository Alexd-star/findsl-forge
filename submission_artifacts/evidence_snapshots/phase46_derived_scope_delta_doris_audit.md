# 官方漏斗差量 Doris 执行审计

- Git HEAD：`f1c0081450ab6790f82c4618784ba93287feb147`
- 状态：`PASS`
- 真实执行通过：`3/3`
- 每条重复执行：`5` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 753 | direct_column | 0 | 76.910 | 179.134 | PASS | PASS |
| 1264 | composite_grouped_aggregate | 61 | 70.222 | 450.004 | PASS | PASS |
| 1265 | composite_grouped_aggregate | 582 | 68.672 | 319.198 | PASS | PASS |
