# 官方漏斗差量 Doris 执行审计

- Git HEAD：`b38a6a7ba88757b51eba4e900ce2663cef360e50`
- 状态：`PASS`
- 真实执行通过：`7/7`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 71 | direct_column | 10 | 53.454 | 275.696 | PASS | PASS |
| 514 | controlled_expression | 5 | 66.995 | 1466.833 | PASS | PASS |
| 515 | direct_column | 27 | 74.235 | 212.381 | PASS | PASS |
| 633 | direct_column | 5 | 82.873 | 223.211 | PASS | PASS |
| 679 | direct_column | 205 | 45.633 | 207.829 | PASS | PASS |
| 716 | controlled_expression | 1 | 57.620 | 168.174 | PASS | PASS |
| 721 | direct_column | 576 | 73.487 | 202.802 | PASS | PASS |
