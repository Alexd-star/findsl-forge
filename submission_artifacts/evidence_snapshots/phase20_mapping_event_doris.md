# Phase 20 受控映射与窗口事件真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`7748d906a90ec13a5e8c539f06d1390dc577d7ff`
- 最新交易日：`2026-04-14`
- 完整结果集哈希一致：`13/13`
- 非空结果：`13/13`
- 每条生成 SQL 重复执行：`5` 次

| 用例 | 期望行数 | 实际行数 | 哈希一致 | 非空 | P95/ms |
|---|---:|---:|---|---|---:|
| `circulating_market_value` | 3083 | 3083 | PASS | yes | 373.8582 |
| `order_imbalance_ratio` | 210 | 210 | PASS | yes | 178.5155 |
| `technical_boolean_composition` | 47 | 47 | PASS | yes | 336.5721 |
| `main_buy_percentage` | 154 | 154 | PASS | yes | 257.6663 |
| `limit_break_event` | 70 | 70 | PASS | yes | 639.2188 |
| `technical_cross_above` | 887 | 887 | PASS | yes | 3046.7137 |
| `cross_resource_cross_down` | 94 | 94 | PASS | yes | 2190.7824 |
| `record_high_60_sessions` | 219 | 219 | PASS | yes | 1188.0490 |
| `record_low_history` | 4 | 4 | PASS | yes | 1034.4625 |
| `event_with_scalar_projection` | 887 | 887 | PASS | yes | 2274.2413 |
| `close_together_pattern` | 3598 | 3598 | PASS | yes | 1467.4013 |
| `reset_pattern` | 1449 | 1449 | PASS | yes | 1195.8313 |
| `position_10_sessions` | 1720 | 1720 | PASS | yes | 1421.0796 |

每个用例均保存生成 SQL、独立参考 SQL、完整结果集 SHA-256 和 EXPLAIN 摘要。
空结果不会自动判错，但会在表格中单独标识，避免把两个空集合的相等误写成强正确性证据。
