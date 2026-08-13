# 十二类函数 Capability Matrix

- Git HEAD：`10b7af790420e2727fa654e84128de24b1f8992f`
- 正式样例：`240`
- 编译成功：`240`
- 十二类覆盖：`True`
- 总门禁：`PASS`

| 函数族 | Reference | 混合组合 | Parser | Typed AST | Logical IR | Rule Contract | Physical IR | Doris SQL | 计划族 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `belong_industry` | 25 | 25 | PASS | PASS | PASS | PASS | PASS | PASS | 46_derived_scope_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition |
| `close_together` | 27 | 24 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window, temporal_event_projection |
| `cross_above` | 22 | 19 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window, event_candidate_intersect, set_intersect, temporal_event_projection |
| `cross_down` | 26 | 24 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window_absence, event_candidate_intersect, set_intersect |
| `golden_cross` | 28 | 26 | PASS | PASS | PASS | PASS | PASS | PASS | adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, temporal_event_projection |
| `indicator` | 204 | 137 | PASS | PASS | PASS | PASS | PASS | PASS | 10_join_doris, 11_date_doris, 12_session_doris, 13_market_doris, 14_aggregate_doris, 15_universe_doris, 16_composite_doris, 17_rank_doris, 18_dynamic_date_doris, 19_security_scope_doris, 20_mapping_event_doris, 21_aggregate_rank_doris, 46_derived_scope_doris, 47_benchmark_policy_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, composite_grouped_aggregate, configured_expression_template, controlled_expression, crossing_window, direct_column, event_candidate_intersect, grouped_aggregate, named_rank_expression, prefix_long_horizon, set_union, stable_temporal_join, stage_rank, temporal_grouped_aggregate |
| `position` | 25 | 21 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window, event_candidate_intersect, stage_rank, temporal_event_projection |
| `queryData` | 30 | 30 | PASS | PASS | PASS | PASS | PASS | PASS | 19_security_scope_doris, 47_benchmark_policy_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, composite_grouped_aggregate, event_candidate_intersect |
| `rank` | 41 | 30 | PASS | PASS | PASS | PASS | PASS | PASS | 17_rank_doris, 19_security_scope_doris, 21_aggregate_rank_doris, 47_benchmark_policy_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, direct_column, named_rank_expression, set_union, stage_rank, temporal_rank |
| `record_high` | 26 | 24 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window, event_candidate_intersect |
| `record_low` | 23 | 19 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window, temporal_event_projection |
| `reset` | 24 | 21 | PASS | PASS | PASS | PASS | PASS | PASS | 20_mapping_event_doris, adversarial_and_or, adversarial_intersection, adversarial_or_and, adversarial_union, balanced_cross_function_composition, crossing_window, set_intersect, temporal_event_projection |
