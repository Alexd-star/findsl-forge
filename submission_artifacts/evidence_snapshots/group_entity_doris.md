# 群组结果实体 Doris 真值证据

- 状态：`PASS`
- Git HEAD：`6d8102471b8fd6ef93435536948f594de829b14c`
- 隔离快照：`findsl-group-oracle-2026-04-14-v1`
- 实验后清理：`True`

| 用例 | 生成结果 | Reference 结果 | 完整行集一致 | EXPLAIN 成员表 |
|---|---:|---:|---|---|
| `group_volume_sum` | 1 | 1 | `True` | `True` |
| `group_float_cap_weighted_return` | 1 | 1 | `True` | `True` |

> 该证据使用独立两只证券成员夹具，仅用于验证群组计划和聚合公式；它不会被计入公开数据快照，实验结束后自动删除。
