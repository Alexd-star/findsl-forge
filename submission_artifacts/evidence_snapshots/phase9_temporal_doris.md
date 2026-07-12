# Phase 9 交易序列时序语义真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`a508dcb4cc2bbf15c38ac37bd236dbde08f40e41`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- MySQL 协议兼容版本：`5.7.99`
- 官方基础表行数：`13650347`
- 独立 oracle 行数：`56149`
- 最新交易日股票数：`5614`
- 行集哈希一致：`4/4`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |
|---|---:|---:|---|---:|
| volume_recent_10_cons_3 | 5590 | 5590 | 是 | 553.5713 |
| volume_recent_10_exist_5 | 5570 | 5570 | 是 | 470.1442 |
| volume_this_5_exist | 5575 | 5575 | 是 | 483.7883 |
| volume_this_5_every | 5566 | 5566 | 是 | 491.063 |

> oracle 只从 Doris 提取最近 10 条原始交易记录，时序判定由独立 Python 参考解释器完成；它不复用生成 SQL 的窗口/CTE 逻辑。
