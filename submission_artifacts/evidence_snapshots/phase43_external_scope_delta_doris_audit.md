# 官方漏斗差量 Doris 执行审计

- Git HEAD：`ffb15c32810dcc02c47252fb1e3fc0a19b640269`
- 状态：`PASS`
- 真实执行通过：`21/21`
- 每条重复执行：`3` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 128 | controlled_expression | 1 | 236.156 | 253.907 | PASS | PASS |
| 152 | set_intersect | 0 | 347.530 | 416.975 | PASS | PASS |
| 220 | controlled_expression | 0 | 249.343 | 321.823 | PASS | PASS |
| 337 | set_intersect | 0 | 1430.371 | 1625.697 | PASS | PASS |
| 404 | direct_column | 93 | 108.470 | 114.896 | PASS | PASS |
| 470 | controlled_expression | 0 | 440.529 | 562.141 | PASS | PASS |
| 517 | direct_column | 0 | 177.676 | 229.843 | PASS | PASS |
| 713 | direct_column | 436 | 243.790 | 247.064 | PASS | PASS |
| 822 | set_union | 2 | 283.572 | 471.054 | PASS | PASS |
| 829 | direct_column | 18 | 123.194 | 125.159 | PASS | PASS |
| 1082 | stage_rank | 30 | 685.320 | 833.614 | PASS | PASS |
| 1133 | aggregate_rank | 1 | 163.600 | 195.877 | PASS | PASS |
| 1148 | composite_grouped_aggregate | 0 | 250.154 | 266.292 | PASS | PASS |
| 1191 | direct_column | 30 | 790.077 | 850.520 | PASS | PASS |
| 1396 | temporal_rank | 0 | 261.999 | 264.306 | PASS | PASS |
| 1560 | direct_column | 0 | 112.732 | 115.325 | PASS | PASS |
| 1735 | controlled_expression | 5 | 775.827 | 776.492 | PASS | PASS |
| 1831 | controlled_expression | 0 | 186.885 | 213.132 | PASS | PASS |
| 1991 | composite_grouped_aggregate | 0 | 776.724 | 819.811 | PASS | PASS |
| 4516 | direct_column | 3 | 124.461 | 141.238 | PASS | PASS |
| 5314 | stable_key_join | 4546 | 2380.246 | 2389.109 | PASS | PASS |
