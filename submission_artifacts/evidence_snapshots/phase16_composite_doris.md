# Phase 16 命名组合聚合真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`d5308b1341eacb00e23ea567de7f82de786e41bd`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- 基础行情表：`13650347` 行
- 完整行集哈希一致：`4/4`
- 集合式命名度量计划：`4/4`
- 安全除零：`4/4`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | 集合式 | P95 ms |
|---|---:|---:|---|---|---:|
| latest_equals_min_100_sessions | 72 | 72 | 是 | 是 | 39.0374 |
| cross_resource_average_ratio | 5269 | 5269 | 是 | 是 | 692.1908 |
| two_windows_with_latest_scalar | 0 | 0 | 是 | 是 | 49.7445 |
| nonempty_two_window_comparison | 5539 | 5539 | 是 | 是 | 447.7 |

> 每个 reference SQL 都独立声明交易日集合、GROUP BY 度量关系和稳定键 Join；编译器 SQL 由 PhysicalAggregateGroup/PhysicalAggregateRef 经 SQLGlot AST 生成。旧路径曾静默忽略的增长、时序聚合和 rank 聚合不计入成功，继续返回专属诊断。
