# Phase 26 日期代数与开放分页真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`aedc7006956a29209acc64d59ff0926dc6ebdf54`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`6/6`
- 非空结果：`6/6`

| 用例 | 物理策略 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---|---:|---:|---|---|---:|
| `fixed_year_following_range` | `grouped_aggregate` | 2933 | 2933 | PASS | yes | 211.6216 |
| `session_before_anchor_day` | `direct_column` | 5562 | 5562 | PASS | yes | 732.5326 |
| `sessions_after_anchor_day_every` | `direct_column` | 5556 | 5556 | PASS | yes | 257.8202 |
| `recent_half_year_aggregate` | `grouped_aggregate` | 5587 | 5587 | PASS | yes | 269.4828 |
| `fractional_year_to_six_month_buckets` | `temporal_grouped_aggregate` | 5537 | 5537 | PASS | yes | 336.4988 |
| `deterministic_open_ended_limit` | `direct_column` | 5566 | 5566 | PASS | yes | 132.7357 |

每组均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256、差异样本和 EXPLAIN 摘要。
参考 SQL 独立实现固定年份区间、锚点交易日、半年范围、六个月连续桶和稳定开放分页，不调用编译器 AST。
