# Phase 9 交易序列时序语义真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`68633028de4b13af9f60b6964532ac7b4f822171`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- MySQL 协议兼容版本：`5.7.99`
- 官方基础表行数：`13650347`
- 独立 oracle 行数：`56149`
- 最新交易日股票数：`5614`
- 行集哈希一致：`6/6`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |
|---|---:|---:|---|---:|
| volume_recent_10_cons_3 | 5590 | 5590 | 是 | 995.613 |
| volume_recent_10_exist_5 | 5570 | 5570 | 是 | 672.7702 |
| volume_this_5_exist | 5575 | 5575 | 是 | 629.0977 |
| volume_this_5_every | 5566 | 5566 | 是 | 517.9561 |
| volume_turnover_temporal_intersection | 5573 | 5573 | 是 | 1104.0876 |
| volume_main_inflow_temporal_union | 5575 | 5575 | 是 | 1357.0546 |

> oracle 只从 Doris 提取最近 10 条原始交易记录，时序判定由独立 Python 参考解释器完成；它不复用生成 SQL 的窗口/CTE 逻辑。
