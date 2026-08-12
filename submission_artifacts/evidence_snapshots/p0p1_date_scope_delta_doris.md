# 官方漏斗差量 Doris 执行审计

- Git HEAD：`414a9803964a61ffa1876b9d1bbda0fba0e6a298`
- 状态：`PASS`
- 真实执行通过：`7/7`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 194 | controlled_expression | 911 | 55.170 | 130.115 | PASS | PASS |
| 195 | controlled_expression | 0 | 38.762 | 120.068 | PASS | PASS |
| 238 | controlled_expression | 0 | 38.450 | 41.577 | PASS | PASS |
| 268 | controlled_expression | 2 | 35.194 | 93.352 | PASS | PASS |
| 649 | controlled_expression | 30 | 35.220 | 105.387 | PASS | PASS |
| 1179 | direct_column | 21908 | 120.397 | 126.426 | PASS | PASS |
| 1736 | controlled_expression | 4198 | 100.837 | 106.067 | PASS | PASS |
