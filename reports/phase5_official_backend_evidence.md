# Phase 5 Doris 物理后端官方证据

- 静态门禁：`PASS`
- 官方问句：`5799`
- Typed AST：`5695`
- Logical IR：`1322`
- Physical IR：`33`
- SQLGlot Doris round-trip：`33`
- 安全 lint：`33`
- 端到端 P95：`10.2284` ms

## 分层门禁

| 门禁 | 状态 |
|---|---|
| static_backend | PASS |
| compile_latency | PASS |
| phase1_4_baseline | PASS |
| structural_diff | PASS |
| real_doris_equivalence | PASS |
| phase5_completion | PASS |

## 真实 Doris 结果等价

| 指标 | 数量/数值 |
|---|---:|
| 静态候选 | 33 |
| 确定性可比 | 30 |
| 实际比较 | 30 |
| 结果匹配 | 30 |
| 结果不匹配 | 0 |
| 跳过 | 3 |
| 执行错误 | 0 |
| 旧后端 P95 | 12248.8166 ms |
| 新后端 P95 | 11814.995 ms |

> 无同层 ORDER BY 的 LIMIT 查询不具备可重复行集，按 NONDETERMINISTIC_LIMIT 记录并排除出结果等价分母；它们不会被计为通过。

## 失败分类

| 错误码 | 数量 |
|---|---:|
| DOMAIN_DATA_UNAVAILABLE | 3819 |
| PHYSICAL_CONSTRAINT_UNSUPPORTED | 661 |
| PHYSICAL_PLAN_UNAVAILABLE | 445 |
| DOMAIN_CAPABILITY_UNSUPPORTED | 430 |
| UNSUPPORTED_LOGICAL_LOWERING | 124 |
| OFFICIAL_TYPE_ERROR | 97 |
| PHYSICAL_EXPRESSION_UNSUPPORTED | 92 |
| PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED | 37 |
| PHYSICAL_MARKET_CONSTRAINT_UNSUPPORTED | 26 |
| PHYSICAL_MULTI_RESOURCE_UNSUPPORTED | 15 |
| PHYSICAL_APPROXIMATION_POLICY_MISSING | 5 |
| OFFICIAL_ANTLR_LEX_ERROR | 5 |
| PHYSICAL_RANK_EXPRESSION_UNSUPPORTED | 4 |
| PHYSICAL_RANK_BOUND_UNSUPPORTED | 4 |
| OFFICIAL_ANTLR_PARSE_ERROR | 2 |