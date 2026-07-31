# 官方漏斗差量 Doris 执行审计

- Git HEAD：`6163f69c709def8ee28a495e68b03fdd7ca35eb9`
- 状态：`PASS`
- 真实执行通过：`23/23`
- 每条重复执行：`5` 次
- 性能阈值：`10000 ms`

| Excel 行 | 策略 | 行数 | P50(ms) | P95(ms) | 哈希稳定 | 状态 |
|---:|---|---:|---:|---:|---|---|
| 321 | crossing_window | 0 | 390.784 | 839.191 | PASS | PASS |
| 407 | controlled_expression | 0 | 326.524 | 432.847 | PASS | PASS |
| 436 | controlled_expression | 156 | 287.463 | 386.811 | PASS | PASS |
| 477 | controlled_expression | 0 | 2976.344 | 7781.178 | PASS | PASS |
| 501 | direct_column | 0 | 57.893 | 257.335 | PASS | PASS |
| 558 | crossing_window | 0 | 59.781 | 290.330 | PASS | PASS |
| 579 | controlled_expression | 0 | 70.042 | 239.525 | PASS | PASS |
| 593 | direct_column | 1 | 57.395 | 230.479 | PASS | PASS |
| 674 | controlled_expression | 1 | 51.586 | 315.859 | PASS | PASS |
| 724 | direct_column | 1 | 62.194 | 461.571 | PASS | PASS |
| 738 | stable_key_join | 0 | 69.769 | 339.208 | PASS | PASS |
| 745 | direct_column | 88 | 86.708 | 241.489 | PASS | PASS |
| 751 | direct_column | 1220 | 78.916 | 234.661 | PASS | PASS |
| 772 | direct_column | 4 | 66.711 | 506.183 | PASS | PASS |
| 826 | stage_rank | 3 | 63.673 | 1057.049 | PASS | PASS |
| 1018 | controlled_expression | 5614 | 1099.076 | 1249.661 | PASS | PASS |
| 1031 | controlled_expression | 5614 | 495.790 | 658.365 | PASS | PASS |
| 1143 | grouped_aggregate | 0 | 47.833 | 243.094 | PASS | PASS |
| 1299 | composite_grouped_aggregate | 0 | 57.279 | 745.120 | PASS | PASS |
| 1962 | controlled_expression | 0 | 56.829 | 312.636 | PASS | PASS |
| 3396 | direct_column | 0 | 83.320 | 250.815 | PASS | PASS |
| 3714 | crossing_window | 8 | 78.015 | 1537.196 | PASS | PASS |
| 5012 | set_intersect | 8 | 70.221 | 3009.597 | PASS | PASS |
