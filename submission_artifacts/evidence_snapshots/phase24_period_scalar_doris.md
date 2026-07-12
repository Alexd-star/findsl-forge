# Phase 24 命名周期标量真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`c34bb57d344a9b97886ed4d0354d88de7e9586e9`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`4/4`
- 非空结果：`4/4`

| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---|---:|---:|---|---|---:|
| `period_scalar_vs_period_average` | `composite_grouped_aggregate` | 2633 | 2633 | PASS | yes | 312.0671 |
| `two_period_scalars_and_aggregate` | `composite_grouped_aggregate` | 5575 | 5575 | PASS | yes | 472.0212 |
| `period_querydata_cross_scalar` | `composite_grouped_aggregate` | 5115 | 5115 | PASS | yes | 290.7347 |
| `period_scalar_with_rank_arithmetic` | `named_rank_expression` | 2888 | 2888 | PASS | yes | 339.2790 |

每组均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本和 EXPLAIN 摘要。
参考 SQL 独立计算周期末值、周期聚合、指定证券标量和横截面排名，不调用编译器 AST。
