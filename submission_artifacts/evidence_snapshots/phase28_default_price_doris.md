# Phase 28 默认价格事件 Doris 证据

- Git HEAD：`a42cd26871f1f8e014c7bbb95b7f760a22151094`
- 最新数据日：`2026-04-14`
- 状态：`PASS`
- 完整行集哈希一致：`6/6`
- 非空结果：`6/6`
- 结构合同通过：`6/6`

| 场景 | 策略 | 参考/实际行数 | P95(ms) | 哈希一致 | 非空 | 结构合同 |
|---|---|---:|---:|---|---|---|
| price_crosses_above_ma20 | crossing_window | 768/768 | 2320.7021 | PASS | PASS | PASS |
| price_does_not_cross_below_ma60 | crossing_window_absence | 5547/5547 | 3177.3871 | PASS | PASS | PASS |
| price_at_five_session_low | crossing_window | 919/919 | 976.3866 | PASS | PASS | PASS |
| price_in_low_historical_quartile | crossing_window | 797/797 | 1241.8526 | PASS | PASS | PASS |
| price_close_to_ma20 | crossing_window | 3018/3018 | 1184.1075 | PASS | PASS | PASS |
| price_resets_to_ma5 | crossing_window | 2855/2855 | 1024.1715 | PASS | PASS | PASS |
