# Phase 7 官方编译器迁移覆盖漏斗

- Git HEAD：`ec7ba60736a26b332d593ff029d9f2db889643a6`
- 官方语料：`5799`
- 旧严格后端成功集：`1097`
- 新后端成功：`33`
- 旧严格后端成功集已迁移：`33/1097`（`3.01%`）

## 阶段漏斗

| 阶段 | 成功数 | 占总语料 |
|---|---:|---:|
| frontend | 5792 | 99.88% |
| typed | 5695 | 98.21% |
| logical | 1322 | 22.80% |
| optimizer | 1322 | 22.80% |
| physical | 33 | 0.57% |
| backend | 33 | 0.57% |

## 迁移缺口优先级

| 错误码 | 旧后端成功但新后端失败 |
|---|---:|
| `PHYSICAL_CONSTRAINT_UNSUPPORTED` | 326 |
| `PHYSICAL_PLAN_UNAVAILABLE` | 305 |
| `DOMAIN_CAPABILITY_UNSUPPORTED` | 230 |
| `PHYSICAL_EXPRESSION_UNSUPPORTED` | 63 |
| `UNSUPPORTED_LOGICAL_LOWERING` | 56 |
| `PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED` | 23 |
| `DOMAIN_DATA_UNAVAILABLE` | 22 |
| `PHYSICAL_MARKET_CONSTRAINT_UNSUPPORTED` | 17 |
| `PHYSICAL_MULTI_RESOURCE_UNSUPPORTED` | 10 |
| `PHYSICAL_APPROXIMATION_POLICY_MISSING` | 5 |
| `PHYSICAL_RANK_BOUND_UNSUPPORTED` | 4 |
| `PHYSICAL_RANK_EXPRESSION_UNSUPPORTED` | 3 |

## 口径说明

不得把 5799 条总语料直接作为 SQL 正确率分母。缺失官方数据域、官方语法缺陷和明确不支持的能力必须分开统计；迁移率只回答旧严格后端已经成功的能力有多少进入了新 ANTLR/IR/SQLGlot 后端。

下一阶段优先处理迁移缺口表中数量最高且具备真实数据字段的错误码。缺失数据域继续返回确定性拒绝，不生成不可执行 SQL。
