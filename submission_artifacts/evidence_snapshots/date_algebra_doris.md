# 日期代数 Doris 真值证据

- 状态：`PASS`
- Git HEAD：`930fadf5cb4a772c737ee9ff1a9cee4b47babc91`
- 用例数：`4`

| 用例 | 生成结果行数 | Reference 行数 | 日期集合 | 完整行集一致 | EXPLAIN 日期谓词 |
|---|---:|---:|---|---|---|
| `calendar_week_ago` | 5556 | 5556 | `2026-04-07` | `True` | `True` |
| `previous_session_before_explicit_date` | 5440 | 5440 | `2025-04-30` | `True` | `True` |
| `previous_week_last_session` | 5572 | 5572 | `2026-04-10` | `True` | `True` |
| `current_month_anchor_day` | 5571 | 5571 | `2026-04-13` | `True` | `True` |

> Reference SQL 独立描述交易日边界，不复用编译器生成的日期表达式；比较对象为完整无序结果集，而非抽样行。
