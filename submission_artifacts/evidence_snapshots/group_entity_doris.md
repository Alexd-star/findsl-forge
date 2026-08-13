# 群组结果实体 Doris 真值证据

- 状态：`PASS`
- Git HEAD：`10b7af790420e2727fa654e84128de24b1f8992f`
- 隔离快照：`findsl-group-oracle-2026-04-14-v1`
- 实验后清理：`True`

| 用例 | 生成结果 | Reference 结果 | 完整行集一致 | EXPLAIN 成员表 |
|---|---:|---:|---|---|
| `group_volume_sum` | 1 | 1 | `True` | `True` |
| `group_float_cap_weighted_return` | 1 | 1 | `True` | `True` |
| `group_metric_intersection` | 1 | 1 | `True` | `True` |
| `group_stage_candidate_rank` | 1 | 1 | `True` | `True` |
| `group_consecutive_trading_sessions` | 1 | 1 | `True` | `True` |
| `group_exist_zero_hit_preserved` | 1 | 1 | `True` | `True` |

> 该证据使用两个隔离群组夹具，用于验证群组计划、聚合公式、集合运算和候选集阶段排名；它不会被计入公开数据快照，实验结束后自动删除。连续条件按真实交易日序列计算，周末不会被误判为中断。
