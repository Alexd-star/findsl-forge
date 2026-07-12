# Phase 23 复合时序与排名区间真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`a7bc571c871bf7d4e73ea53237bb85e8cf69cc24`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`6/6`
- 非空结果：`6/6`

| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---|---:|---:|---|---|---:|
| `not_every_recent_five` | `direct_column` | 48 | 48 | PASS | yes | 317.2239 |
| `aligned_temporal_arithmetic` | `direct_column` | 5590 | 5590 | PASS | yes | 573.0693 |
| `multi_resource_temporal_join` | `stable_temporal_join` | 2929 | 2929 | PASS | yes | 1122.9697 |
| `direct_rank_percentage_range` | `direct_column` | 282 | 282 | PASS | yes | 144.2110 |
| `candidate_stage_rank_range` | `stage_rank` | 6 | 6 | PASS | yes | 238.3397 |
| `set_candidates_then_rank` | `stage_rank` | 3 | 3 | PASS | yes | 351.9254 |

每组均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本和 EXPLAIN 摘要。
参考 SQL 独立重建时序连续段、跨表稳定键 Join、排名总体及候选阶段，不调用编译器 AST。
