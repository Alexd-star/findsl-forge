# Phase 29 泛化事件投影 Doris 证据

- Git HEAD：`84e86ff1cfcf46237ce014ee4543c2d06d565439`
- 最新数据日：`2026-04-14`
- 状态：`PASS`
- 完整行集哈希一致：`4/4`
- 非空结果：`4/4`
- 结构合同通过：`4/4`
- P95 低于 10 秒：`4/4`

| 场景 | 策略 | 参考/实际行数 | P95(ms) | 哈希一致 | 非空 | 结构合同 |
|---|---|---:|---:|---|---|---|
| consecutive_historical_low_position | temporal_event_projection | 1071/1071 | 48.3308 | PASS | PASS | PASS |
| repeated_twenty_session_low | temporal_event_projection | 4551/4551 | 1512.6686 | PASS | PASS | PASS |
| three_session_price_ma5_convergence | temporal_event_projection | 5444/5444 | 1339.2752 | PASS | PASS | PASS |
| repeated_price_reset_to_ma20 | temporal_event_projection | 3250/3250 | 1394.5923 | PASS | PASS | PASS |
