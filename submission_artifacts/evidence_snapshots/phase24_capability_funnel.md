# 官方编译器迁移覆盖漏斗

- Git HEAD：`c34bb57d344a9b97886ed4d0354d88de7e9586e9`
- 官方语料：`5799`
- 旧严格后端成功集：`1097`
- 新后端成功：`687`
- 旧严格后端成功集已迁移：`667/1097`（`60.80%`）

## 阶段漏斗

| 阶段 | 成功数 | 占总语料 |
|---|---:|---:|
| frontend | 5792 | 99.88% |
| typed | 5695 | 98.21% |
| logical | 1617 | 27.88% |
| optimizer | 1617 | 27.88% |
| physical | 687 | 11.85% |
| backend | 687 | 11.85% |

## 迁移缺口优先级

| 错误码 | 旧后端成功但新后端失败 |
|---|---:|
| `PHYSICAL_SCOPE_DATA_UNAVAILABLE` | 260 |
| `DOMAIN_CAPABILITY_UNSUPPORTED` | 106 |
| `DOMAIN_DATA_UNAVAILABLE` | 22 |
| `PHYSICAL_INDUSTRY_DATA_UNAVAILABLE` | 15 |
| `PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED` | 6 |
| `PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED` | 5 |
| `PHYSICAL_EVENT_DATE_SCOPE_MISMATCH` | 4 |
| `UNSUPPORTED_LOGICAL_LOWERING` | 4 |
| `PHYSICAL_PLAN_UNAVAILABLE` | 3 |
| `PHYSICAL_EVENT_PLAN_UNSUPPORTED` | 2 |
| `TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED` | 1 |
| `TEMPORAL_SCOPE_MISMATCH` | 1 |
| `PHYSICAL_EVENT_PERIOD_UNSUPPORTED` | 1 |

## 口径说明

不得把 5799 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。

下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。
