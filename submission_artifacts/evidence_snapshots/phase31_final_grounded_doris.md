# Phase 31 最终有据迁移缺口 Doris 证据

- Git HEAD：`6ef44126366a9d9fe814dab05a2ed2d934ff958a`
- 状态：`PASS`
- 完整行集哈希一致：`2/2`
- 非空结果：`2/2`
- 结构合同通过：`2/2`
- P95 低于 10 秒：`2/2`

| 场景 | 策略 | 参考/实际行数 | P95(ms) | 哈希一致 | 非空 | 结构合同 |
|---|---|---:|---:|---|---|---|
| fixed_since_record_high | crossing_window | 34/34 | 56.8231 | PASS | PASS | PASS |
| event_candidate_then_rank | stage_rank | 2/2 | 64.6454 | PASS | PASS | PASS |
