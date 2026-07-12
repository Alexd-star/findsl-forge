# 官方编译器迁移覆盖漏斗

- Git HEAD：`70e91d1daacc9ff49945ad32a54456f7d3fcf878`
- 官方语料：`5799`
- 旧严格后端成功集：`1097`
- 新后端成功：`260`
- 旧严格后端成功集已迁移：`258/1097`（`23.52%`）

## 阶段漏斗

| 阶段 | 成功数 | 占总语料 |
|---|---:|---:|
| frontend | 5792 | 99.88% |
| typed | 5695 | 98.21% |
| logical | 1487 | 25.64% |
| optimizer | 1487 | 25.64% |
| physical | 260 | 4.48% |
| backend | 260 | 4.48% |

## 迁移缺口优先级

| 错误码 | 旧后端成功但新后端失败 |
|---|---:|
| `PHYSICAL_CONSTRAINT_UNSUPPORTED` | 227 |
| `DOMAIN_CAPABILITY_UNSUPPORTED` | 106 |
| `PHYSICAL_PLAN_UNAVAILABLE` | 87 |
| `PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED` | 67 |
| `PHYSICAL_EXPRESSION_UNSUPPORTED` | 66 |
| `PHYSICAL_AGGREGATE_COMPOSITION_UNSUPPORTED` | 59 |
| `UNSUPPORTED_LOGICAL_LOWERING` | 57 |
| `PHYSICAL_RANK_EXPRESSION_UNSUPPORTED` | 55 |
| `PHYSICAL_APPROXIMATION_POLICY_MISSING` | 37 |
| `PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED` | 22 |
| `DOMAIN_DATA_UNAVAILABLE` | 22 |
| `PHYSICAL_RANK_BOUND_UNSUPPORTED` | 19 |
| `TEMPORAL_MULTI_PREDICATE_UNSUPPORTED` | 7 |
| `PHYSICAL_LOGICAL_PLAN_UNSUPPORTED` | 4 |
| `PHYSICAL_CHAINED_RANK_UNSUPPORTED` | 2 |
| `TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED` | 1 |
| `TEMPORAL_SCOPE_MISMATCH` | 1 |

## 口径说明

不得把 5799 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。

下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。
