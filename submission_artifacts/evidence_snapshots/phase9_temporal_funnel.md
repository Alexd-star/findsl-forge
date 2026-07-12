# 官方编译器迁移覆盖漏斗

- Git HEAD：`f121041f24503bae0f1741edce35db02c6687cc2`
- 官方语料：`5799`
- 旧严格后端成功集：`1097`
- 新后端成功：`87`
- 旧严格后端成功集已迁移：`87/1097`（`7.93%`）

## 阶段漏斗

| 阶段 | 成功数 | 占总语料 |
|---|---:|---:|
| frontend | 5792 | 99.88% |
| typed | 5695 | 98.21% |
| logical | 1149 | 19.81% |
| optimizer | 1149 | 19.81% |
| physical | 87 | 1.50% |
| backend | 87 | 1.50% |

## 迁移缺口优先级

| 错误码 | 旧后端成功但新后端失败 |
|---|---:|
| `DOMAIN_CAPABILITY_UNSUPPORTED` | 230 |
| `PHYSICAL_CONSTRAINT_UNSUPPORTED` | 213 |
| `PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED` | 79 |
| `PHYSICAL_MULTI_RESOURCE_UNSUPPORTED` | 79 |
| `PHYSICAL_EXPRESSION_UNSUPPORTED` | 71 |
| `PHYSICAL_PLAN_UNAVAILABLE` | 68 |
| `TEMPORAL_COMPOSITE_PREDICATE_UNSUPPORTED` | 68 |
| `UNSUPPORTED_LOGICAL_LOWERING` | 55 |
| `PHYSICAL_MARKET_CONSTRAINT_UNSUPPORTED` | 37 |
| `TEMPORAL_MULTI_PREDICATE_UNSUPPORTED` | 31 |
| `DOMAIN_DATA_UNAVAILABLE` | 22 |
| `PHYSICAL_RANK_EXPRESSION_UNSUPPORTED` | 17 |
| `PHYSICAL_APPROXIMATION_POLICY_MISSING` | 16 |
| `PHYSICAL_TEMPORAL_BUCKET_UNSUPPORTED` | 14 |
| `PHYSICAL_RANK_BOUND_UNSUPPORTED` | 9 |
| `TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED` | 1 |

## 口径说明

不得把 5799 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。

下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。
