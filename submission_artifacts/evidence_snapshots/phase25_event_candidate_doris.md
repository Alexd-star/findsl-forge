# Phase 25 证券键事件候选关系真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`f95e142df6800189acfcfcfd876e5f2f0bc2d3e3`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`5/5`
- 非空结果：`5/5`

| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---|---:|---:|---|---|---:|
| `period_record_high_and_grouped_average` | `event_candidate_intersect` | 1196 | 1196 | PASS | yes | 44.1237 |
| `period_event_absence_uses_decidable_universe` | `event_candidate_intersect` | 4453 | 4453 | PASS | yes | 2163.5640 |
| `latest_position_and_exact_security_scalar` | `event_candidate_intersect` | 78 | 78 | PASS | yes | 41.9558 |
| `event_union_and_multi_growth_relation` | `event_candidate_intersect` | 442 | 442 | PASS | yes | 41.5466 |
| `different_event_and_indicator_date_scopes` | `event_candidate_intersect` | 299 | 299 | PASS | yes | 49.4349 |

每组均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本和 EXPLAIN 摘要。
参考 SQL 独立实现证券键集合交并差、事件窗口、三值可判定全集、最新快照回连和聚合关系，不调用编译器 AST。
