# Phase 27 事件语义 Doris 证据

- Git HEAD：`0386df26d7abff608551001c6fe545b3ea9386b6`
- 最新数据日：`2026-04-14`
- 状态：`PASS`
- 完整行集哈希一致：`4/4`
- 非空结果：`4/4`
- 结构合同通过：`4/4`

| 场景 | 策略 | 参考/实际行数 | P95(ms) | 哈希一致 | 非空 | 结构合同 |
|---|---|---:|---:|---|---|---|
| bounded_crossing_existence | temporal_event_projection | 4870/4870 | 2090.4077 | PASS | PASS | PASS |
| monthly_crossing_bucket | temporal_event_projection | 1659/1659 | 47.5576 | PASS | PASS | PASS |
| cross_date_event_intersection | event_candidate_intersect | 5570/5570 | 1902.3641 | PASS | PASS | PASS |
| eighty_session_extreme_with_latest_scalar | event_candidate_intersect | 57/57 | 38.6546 | PASS | PASS | PASS |
