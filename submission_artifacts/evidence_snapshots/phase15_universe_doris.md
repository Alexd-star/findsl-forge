# Phase 15 类型化证券全集真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`70e91d1daacc9ff49945ad32a54456f7d3fcf878`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- 行集哈希一致：`4/4`
- 无 1=0/1=1 占位：`4/4`
- 显式 all 集合契约：`4/4`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | 无占位 | P95 ms |
|---|---:|---:|---|---|---:|
| full_latest_universe | 5614 | 5614 | 是 | 是 | 288.9052 |
| shanghai_main_latest_universe | 1718 | 1718 | 是 | 是 | 72.6734 |
| exclude_chinext_latest_universe | 4213 | 4213 | 是 | 是 | 177.9478 |
| recent_five_session_universe | 28061 | 28061 | 是 | 是 | 174.7272 |

> reference SQL 直接读取官方 basic 表，并独立表达全市场、板块、补集和最近五个交易日集合；编译器 SQL 由 Typed Universe IR 经 Physical IR 与 SQLGlot AST 生成。概念、行业、指数成员关系因官方数据未提供而继续确定性拒绝。
