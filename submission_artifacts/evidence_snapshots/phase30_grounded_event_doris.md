# Phase 30 有据事件周期与范围 Doris 证据

- Git HEAD：`55183c40104b92abe7e9932d4d33e0c5153d3f73`
- 状态：`PASS`
- 完整行集哈希一致：`6/6`
- 非空结果：`6/6`
- 结构合同通过：`6/6`
- P95 低于 10 秒：`6/6`

| 场景 | 策略 | 参考/实际行数 | P95(ms) | 哈希一致 | 非空 | 结构合同 |
|---|---|---:|---:|---|---|---|
| half_month_price_low | crossing_window | 304/304 | 67.3489 | PASS | PASS | PASS |
| previous_month_price_extreme | crossing_window | 837/837 | 71.6551 | PASS | PASS | PASS |
| exact_security_repeated_crossing | temporal_event_projection | 1/1 | 65.4620 | PASS | PASS | PASS |
| support_reset_and_pressure_crossing | set_intersect | 85/85 | 55.2104 | PASS | PASS | PASS |
| unsealed_limit_event | controlled_expression | 35/35 | 60.8722 | PASS | PASS | PASS |
| half_year_historical_low | crossing_window | 3513/3513 | 1024.4798 | PASS | PASS | PASS |
