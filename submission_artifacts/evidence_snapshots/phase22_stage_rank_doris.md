# Phase 22 命名排名与候选集阶段真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`44c3b32a1a0a46e4ffdf7f57986c3aa87d0b463f`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`7/7`
- 非空结果：`7/7`

| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---|---:|---:|---|---|---:|
| `named_rank_arithmetic` | `named_rank_expression` | 2927 | 2927 | PASS | yes | 333.7435 |
| `named_rank_period_end_arithmetic` | `named_rank_expression` | 2937 | 2937 | PASS | yes | 258.0705 |
| `chained_candidate_rank` | `stage_rank` | 5 | 5 | PASS | yes | 297.4412 |
| `aggregate_filter_then_rank` | `stage_rank` | 80 | 80 | PASS | yes | 264.8705 |
| `temporal_filter_then_period_rank` | `stage_rank` | 278 | 278 | PASS | yes | 411.3313 |
| `parenthesized_stage_union` | `set_union` | 1 | 1 | PASS | yes | 294.7526 |
| `temporal_rank_percentage_range` | `temporal_rank` | 377 | 377 | PASS | yes | 379.1566 |

每个用例保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本与 EXPLAIN 摘要。
参考 SQL 独立表达排名总体、候选集边界和时序连续性，不复用编译器生成 AST。
