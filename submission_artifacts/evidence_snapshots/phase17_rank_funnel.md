# 官方编译器迁移覆盖漏斗

- Git HEAD：`0f3db8648a54f2d50966d91e3aab79dbb9a38aaa`
- 官方语料：`5799`
- 旧严格后端成功集：`1097`
- 新后端成功：`319`
- 旧严格后端成功集已迁移：`317/1097`（`28.90%`）

## 阶段漏斗

| 阶段 | 成功数 | 占总语料 |
|---|---:|---:|
| frontend | 5792 | 99.88% |
| typed | 5695 | 98.21% |
| logical | 1598 | 27.56% |
| optimizer | 1598 | 27.56% |
| physical | 319 | 5.50% |
| backend | 319 | 5.50% |

## 迁移缺口优先级

| 错误码 | 旧后端成功但新后端失败 |
|---|---:|
| `PHYSICAL_CONSTRAINT_UNSUPPORTED` | 259 |
| `DOMAIN_CAPABILITY_UNSUPPORTED` | 106 |
| `PHYSICAL_PLAN_UNAVAILABLE` | 95 |
| `PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED` | 82 |
| `PHYSICAL_EXPRESSION_UNSUPPORTED` | 80 |
| `PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED` | 49 |
| `PHYSICAL_APPROXIMATION_POLICY_MISSING` | 37 |
| `DOMAIN_DATA_UNAVAILABLE` | 22 |
| `PHYSICAL_RANK_EXPRESSION_UNSUPPORTED` | 18 |
| `UNSUPPORTED_LOGICAL_LOWERING` | 10 |
| `TEMPORAL_MULTI_PREDICATE_UNSUPPORTED` | 7 |
| `PHYSICAL_CHAINED_RANK_UNSUPPORTED` | 5 |
| `PHYSICAL_AGGREGATE_COMPOSITION_UNSUPPORTED` | 4 |
| `PHYSICAL_LOGICAL_PLAN_UNSUPPORTED` | 4 |
| `TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED` | 1 |
| `TEMPORAL_SCOPE_MISMATCH` | 1 |

## 口径说明

不得把 5799 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。

下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。
