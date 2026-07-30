# 官方漏斗差量 Doris 执行审计

- Git HEAD：`1146cf0a4cce9b89409285ea194f50024de7d8cb`
- 状态：`PASS`
- 真实执行通过：`8/8`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 239 | direct_column | 0 | 109.831 | 122.348 | PASS | PASS |
| 240 | direct_column | 20 | 223.682 | 227.292 | PASS | PASS |
| 455 | direct_column | 1 | 126.990 | 139.475 | PASS | PASS |
| 807 | stage_rank | 0 | 467.938 | 491.928 | PASS | PASS |
| 981 | controlled_expression | 0 | 628.643 | 702.532 | PASS | PASS |
| 1030 | controlled_expression | 0 | 738.304 | 780.087 | PASS | PASS |
| 1284 | aggregate_rank | 1 | 150.726 | 160.186 | PASS | PASS |
| 5304 | controlled_expression | 3 | 139.735 | 201.981 | PASS | PASS |
