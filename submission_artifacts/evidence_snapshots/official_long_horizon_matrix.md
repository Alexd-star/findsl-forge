# 官方 20 年数据长周期工作负载矩阵

- 状态：`PASS`
- 工作负载：`5`
- 最低加速比：`14.941x`
- 加速比中位数：`15.133x`
- 全部完整结果哈希一致：`True`
- 全部优化 P95 小于 10 秒：`True`

| Workload | 指标 | 聚合 | 基线中位数 ms | 优化中位数 ms | 优化 P95 ms | 加速比 | 哈希一致 | 状态 |
|---|---|---|---:|---:|---:|---:|---:|---|
| LONG-HORIZON-VOLUME-SUM | 成交量 | SUM | 256.000 | 17.000 | 19.000 | 15.059x | True | PASS |
| LONG-HORIZON-VOLUME-AVG | 成交量 | AVG | 227.000 | 15.000 | 22.000 | 15.133x | True | PASS |
| LONG-HORIZON-TURNOVER-SUM | 成交额 | SUM | 263.000 | 16.000 | 20.000 | 16.438x | True | PASS |
| LONG-HORIZON-CLOSE-SUM | 收盘价 | SUM | 249.000 | 16.000 | 20.000 | 15.562x | True | PASS |
| LONG-HORIZON-CLOSE-AVG | 收盘价 | AVG | 254.000 | 17.000 | 20.000 | 14.941x | True | PASS |

## 口径边界

本矩阵只比较五类 5000 个交易日聚合的完整结果和 Doris Profile 耗时。它不与短窗口、集合式前缀或外部集群基准混为一个加速数字。
