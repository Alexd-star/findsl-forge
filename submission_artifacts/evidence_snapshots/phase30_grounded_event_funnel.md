# 官方编译器迁移覆盖漏斗

- Git HEAD：`55183c40104b92abe7e9932d4d33e0c5153d3f73`
- 官方语料：`5799`
- 旧严格后端成功集：`1097`
- 新后端成功：`764`
- 旧严格后端成功集已迁移：`740/1097`（`67.46%`）

## 阶段漏斗

| 阶段 | 成功数 | 占总语料 |
|---|---:|---:|
| frontend | 5792 | 99.88% |
| typed | 5695 | 98.21% |
| logical | 1730 | 29.83% |
| optimizer | 1730 | 29.83% |
| physical | 764 | 13.17% |
| backend | 764 | 13.17% |

## 迁移缺口优先级

| 错误码 | 旧后端成功但新后端失败 |
|---|---:|
| `PHYSICAL_SCOPE_DATA_UNAVAILABLE` | 275 |
| `DOMAIN_CAPABILITY_UNSUPPORTED` | 35 |
| `DOMAIN_DATA_UNAVAILABLE` | 27 |
| `PHYSICAL_INDUSTRY_DATA_UNAVAILABLE` | 15 |
| `PHYSICAL_PLAN_UNAVAILABLE` | 2 |
| `TEMPORAL_SCOPE_MISMATCH` | 1 |
| `PHYSICAL_EVENT_PLAN_UNSUPPORTED` | 1 |
| `PHYSICAL_EVENT_PERIOD_UNSUPPORTED` | 1 |

## 口径说明

不得把 5799 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。

下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。
