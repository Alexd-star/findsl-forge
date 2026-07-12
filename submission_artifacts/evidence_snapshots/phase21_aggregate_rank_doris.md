# Phase 21 近似、聚合与排名真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`be49fdc5b3cc188146ae2a37b1e58ea508dd73ea`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`6/6`
- 非空结果：`6/6`

| 用例 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---:|---:|---|---|---:|
| `configured_relative_approximation` | 38 | 38 | PASS | yes | 163.2676 |
| `five_session_growth_filter` | 1663 | 1663 | PASS | yes | 188.2671 |
| `daily_growth_exist` | 4854 | 4854 | PASS | yes | 507.2428 |
| `daily_max_consecutive` | 5590 | 5590 | PASS | yes | 520.1959 |
| `growth_rank_top10` | 10 | 10 | PASS | yes | 186.8021 |
| `daily_growth_temporal_rank` | 5258 | 5258 | PASS | yes | 511.3864 |

每个用例保存生成 SQL、独立参考 SQL、完整结果集 SHA-256 和 EXPLAIN 摘要。
参考 SQL 独立写出数学与集合语义，不复用编译器生成 AST。
