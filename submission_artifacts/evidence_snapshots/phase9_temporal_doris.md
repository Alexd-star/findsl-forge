# Phase 9 交易序列时序语义真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`aeb4f987cffd0246e1c2a15f889cdbe0970896c3`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- MySQL 协议兼容版本：`5.7.99`
- 官方基础表行数：`13650347`
- 独立 oracle 行数：`56149`
- 日历桶 oracle：`94323` 行 / `200` 只固定样本股票
- 最新交易日股票数：`5614`
- 行集哈希一致：`10/10`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |
|---|---:|---:|---|---:|
| volume_recent_10_cons_3 | 5590 | 5590 | 是 | 657.5021 |
| volume_recent_10_exist_5 | 5570 | 5570 | 是 | 495.1921 |
| volume_this_5_exist | 5575 | 5575 | 是 | 527.5753 |
| volume_this_5_every | 5566 | 5566 | 是 | 521.2775 |
| volume_turnover_temporal_intersection | 5573 | 5573 | 是 | 933.0383 |
| volume_main_inflow_temporal_union | 5575 | 5575 | 是 | 1295.8596 |
| volume_two_year_every_year | 196 | 196 | 是 | 445.8838 |
| volume_two_year_exist_2_months | 200 | 200 | 是 | 482.8577 |
| volume_two_year_cons_3_quarters | 200 | 200 | 是 | 515.2517 |
| volume_two_year_every_week | 0 | 0 | 是 | 456.8481 |

> oracle 从 Doris 提取原始交易记录；日粒度覆盖全体最新股票，日历桶覆盖按稳定键排序的 200 只固定样本股票。时序与缺失桶判定由独立 Python 参考解释器完成，不复用生成 SQL 的窗口、桶或 CTE 逻辑。
