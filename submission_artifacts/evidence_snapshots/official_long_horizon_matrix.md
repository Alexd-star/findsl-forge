# 官方 20 年数据长周期工作负载矩阵

- 状态：`PASS`
- 工作负载：`5`
- 最低加速比：`14.667x`
- 加速比中位数：`15.643x`
- 全部完整结果哈希一致：`True`
- 全部优化 P95 小于 10 秒：`True`

| Workload | 指标 | 聚合 | 基线中位数 ms | 优化中位数 ms | 优化 P95 ms | 加速比 | 哈希一致 | 状态 |
|---|---|---|---:|---:|---:|---:|---:|---|
| LONG-HORIZON-VOLUME-SUM | 成交量 | SUM | 229.000 | 15.000 | 18.000 | 15.267x | True | PASS |
| LONG-HORIZON-VOLUME-AVG | 成交量 | AVG | 219.000 | 14.000 | 32.000 | 15.643x | True | PASS |
| LONG-HORIZON-TURNOVER-SUM | 成交额 | SUM | 220.000 | 15.000 | 17.000 | 14.667x | True | PASS |
| LONG-HORIZON-CLOSE-SUM | 收盘价 | SUM | 262.000 | 15.000 | 16.000 | 17.467x | True | PASS |
| LONG-HORIZON-CLOSE-AVG | 收盘价 | AVG | 287.000 | 14.000 | 15.000 | 20.500x | True | PASS |

## 口径边界

本矩阵只比较五类 5000 个交易日聚合的完整结果和 Doris Profile 耗时。它不与短窗口、集合式前缀或外部集群基准混为一个加速数字。
