# 官方漏斗差量 Doris 执行审计

- Git HEAD：`1021dd93fe1d89e0519d31f91e20cb318bbc740b`
- 状态：`PASS`
- 真实执行通过：`9/9`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 203 | direct_column | 0 | 66.889 | 322.426 | PASS | PASS |
| 213 | direct_column | 190 | 68.616 | 197.736 | PASS | PASS |
| 233 | direct_column | 0 | 58.696 | 194.803 | PASS | PASS |
| 576 | direct_column | 5 | 62.383 | 542.104 | PASS | PASS |
| 1481 | crossing_window | 0 | 52.105 | 257.353 | PASS | PASS |
| 1553 | set_intersect | 0 | 73.963 | 496.030 | PASS | PASS |
| 1718 | controlled_expression | 0 | 54.358 | 310.349 | PASS | PASS |
| 1754 | controlled_expression | 31 | 51.019 | 289.940 | PASS | PASS |
| 3712 | crossing_window | 0 | 197.359 | 1609.634 | PASS | PASS |
