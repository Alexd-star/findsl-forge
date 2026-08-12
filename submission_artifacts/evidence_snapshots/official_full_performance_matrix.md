# 官方真实数据分层性能矩阵

- Git HEAD：`a531f1c42169199bc958ffcbafbf122f0f4928d7`
- Catalog snapshot：`9198d534b9430211f5d24cdf4700f95f761e9e077e5e1cf6bb03d8282b6c1dbd`
- 用例：`48`
- 全部匹配独立 reference：`True`
- 全部 P95 <= 10s：`True`
- 最大 P95：`3151.535` ms

| Case | 函数族 | 计划族 | 策略 | 负载 | Rows | Compile ms | P95 ms | 10s | 状态 |
|---|---|---|---|---|---:|---:|---:|---|---|
| CORR-ADAPTIVE-AGGREGATE-002 | indicator | prefix_long_horizon | volume_prefix_aggregate | heavy | 5614 | 18.8306 | 61.7781 | True | PASS |
| CORR-PHASE10-JOIN-DORIS-001-BASIC-EXT-LATEST | indicator | 10_join_doris | stable_key_join | medium | 2247 | 16.936 | 49.0598 | True | PASS |
| CORR-PHASE10-JOIN-DORIS-002-BASIC-SECURITY-LATEST | indicator | 10_join_doris | stable_key_join | medium | 5573 | 18.7576 | 231.4309 | True | PASS |
| CORR-PHASE11-DATE-DORIS-001-CHINESE-YEAR-2024 | indicator | 11_date_doris | direct_column | medium | 16734 | 16.7568 | 86.1516 | True | PASS |
| CORR-PHASE12-SESSION-DORIS-001-RECENT-5-SESSIONS | indicator | 12_session_doris | direct_column | medium | 467 | 11.8301 | 78.9329 | True | PASS |
| CORR-PHASE13-MARKET-DORIS-001-STAR-MARKET | indicator | 13_market_doris | direct_column | medium | 606 | 12.6297 | 70.2209 | True | PASS |
| CORR-PHASE14-AGGREGATE-DORIS-001-SUM-VOLUME-5 | indicator | 14_aggregate_doris | grouped_aggregate | medium | 574 | 15.4819 | 69.5777 | True | PASS |
| CORR-PHASE15-UNIVERSE-DORIS-001-FULL-LATEST-UNIVERSE | indicator | 15_universe_doris | direct_column | medium | 5614 | 9.268 | 150.6038 | True | PASS |
| CORR-PHASE16-COMPOSITE-DORIS-001-LATEST-EQUALS-MIN-100-SESSIONS | indicator | 16_composite_doris | composite_grouped_aggregate | medium | 72 | 14.2996 | 40.7246 | True | PASS |
| CORR-PHASE17-RANK-DORIS-001-DIRECT-TOP-10 | rank | 17_rank_doris | direct_column | medium | 10 | 12.2635 | 52.7039 | True | PASS |
| CORR-PHASE17-RANK-DORIS-002-DIRECT-TOP-10-PERCENT | rank | 17_rank_doris | direct_column | medium | 562 | 13.2725 | 71.0699 | True | PASS |
| CORR-PHASE17-RANK-DORIS-003-AGGREGATE-AVG-TOP-10 | rank | 17_rank_doris | aggregate_rank | medium | 10 | 14.8499 | 44.2142 | True | PASS |
| CORR-PHASE18-DYNAMIC-DATE-DORIS-001-CURRENT-MONTH | indicator | 18_dynamic_date_doris | direct_column | medium | 867 | 12.2747 | 76.4548 | True | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | medium | 1896 | 24.1418 | 48.6945 | True | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-005-GLOBAL-QUERYDATA-AGGREGATE | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | medium | 1872 | 21.2987 | 48.1899 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE | cross_above | 20_mapping_event_doris | crossing_window | medium | 887 | 15.7474 | 52.1143 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS | record_high | 20_mapping_event_doris | crossing_window | medium | 219 | 15.2758 | 56.0007 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY | record_low | 20_mapping_event_doris | crossing_window | medium | 4 | 11.563 | 44.9697 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN | close_together | 20_mapping_event_doris | crossing_window | medium | 3598 | 14.774 | 962.3106 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN | reset | 20_mapping_event_doris | crossing_window | medium | 1449 | 16.4426 | 44.087 | True | PASS |
| CORR-PHASE21-AGGREGATE-RANK-DORIS-001-CONFIGURED-RELATIVE-APPROXIMATIO | indicator | 21_aggregate_rank_doris | controlled_expression | medium | 38 | 15.3743 | 47.4978 | True | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-001-NAMED-RANK-ARITHMETIC | rank | named_rank_expression | named_rank_expression | medium | 2927 | 25.3527 | 51.1614 | True | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-006-PARENTHESIZED-STAGE-UNION | indicator,rank | set_union | set_union | medium | 1 | 63.7046 | 44.8623 | True | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-001-NOT-EVERY-RECENT-FIVE | indicator | direct_column | direct_column | light | 48 | 16.9393 | 46.2771 | True | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-003-MULTI-RESOURCE-TEMPORAL-JOIN | indicator | stable_temporal_join | stable_temporal_join | heavy | 2929 | 27.6085 | 46.7036 | True | PASS |
| CORR-PHASE24-PERIOD-SCALAR-DORIS-003-PERIOD-QUERYDATA-CROSS-SCALAR | indicator,queryData | composite_grouped_aggregate | composite_grouped_aggregate | heavy | 5115 | 25.1251 | 266.5977 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-001-PERIOD-RECORD-HIGH-AND-GROUPED-A | indicator,record_high | event_candidate_intersect | event_candidate_intersect | heavy | 1196 | 24.8818 | 48.3813 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-002-PERIOD-EVENT-ABSENCE-USES-DECIDA | cross_down,indicator | event_candidate_intersect | event_candidate_intersect | heavy | 4453 | 30.515 | 2585.4578 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-004-EVENT-UNION-AND-MULTI-GROWTH-REL | cross_above,cross_down,indicator | event_candidate_intersect | event_candidate_intersect | heavy | 442 | 78.3918 | 48.3776 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-005-DIFFERENT-EVENT-AND-INDICATOR-DA | indicator,record_high | event_candidate_intersect | event_candidate_intersect | heavy | 299 | 21.1307 | 43.3484 | True | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-001-FIXED-YEAR-FOLLOWING-RANGE | indicator | grouped_aggregate | grouped_aggregate | medium | 2933 | 17.5891 | 48.8563 | True | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-005-FRACTIONAL-YEAR-TO-SIX-MONTH-BUC | indicator | temporal_grouped_aggregate | temporal_grouped_aggregate | heavy | 5537 | 25.869 | 355.2395 | True | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE | golden_cross | temporal_event_projection | temporal_event_projection | heavy | 4870 | 19.4307 | 2318.8144 | True | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-002-MONTHLY-CROSSING-BUCKET | golden_cross | temporal_event_projection | temporal_event_projection | heavy | 1659 | 22.0591 | 74.8968 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-002-PRICE-DOES-NOT-CROSS-BELOW-MA60 | cross_down | crossing_window_absence | crossing_window_absence | heavy | 5547 | 20.6558 | 3151.535 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-003-PRICE-AT-FIVE-SESSION-LOW | record_low | crossing_window | crossing_window | heavy | 919 | 12.9438 | 46.6254 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-004-PRICE-IN-LOW-HISTORICAL-QUARTILE | position | crossing_window | crossing_window | heavy | 797 | 16.7166 | 44.558 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-005-PRICE-CLOSE-TO-MA20 | close_together | crossing_window | crossing_window | heavy | 3018 | 14.2302 | 942.7636 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-006-PRICE-RESETS-TO-MA5 | reset | crossing_window | crossing_window | heavy | 2855 | 16.4578 | 46.2039 | True | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-002-REPEATED-TWENTY-SESSION-LOW | record_low | temporal_event_projection | temporal_event_projection | heavy | 4551 | 21.5766 | 1061.22 | True | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-003-THREE-SESSION-PRICE-MA5-CONVERGE | close_together | temporal_event_projection | temporal_event_projection | heavy | 5444 | 49.6456 | 1156.8201 | True | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-004-SUPPORT-RESET-AND-PRESSURE-CROSS | cross_above,cross_down,reset | set_intersect | set_intersect | medium | 85 | 39.6635 | 43.5318 | True | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-005-UNSEALED-LIMIT-EVENT | indicator | controlled_expression | controlled_expression | light | 35 | 15.1203 | 43.0346 | True | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-006-HALF-YEAR-HISTORICAL-LOW | position | crossing_window | crossing_window | heavy | 3513 | 13.5694 | 993.1937 | True | PASS |
| CORR-PHASE31-FINAL-GROUNDED-DORIS-002-EVENT-CANDIDATE-THEN-RANK | indicator,position,rank | stage_rank | stage_rank | heavy | 2 | 49.1268 | 43.2519 | True | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-002-CSI300-SSE-MAIN-BOARD-INDUSTRY-A | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | medium | 61 | 61.5135 | 50.2231 | True | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | medium | 582 | 23.9008 | 48.25 | True | PASS |
| CORR-PHASE47-BENCHMARK-POLICY-DORIS-001-AI-TOP1-NOT-OUTPERFORM-BENCHMARK | indicator,queryData,rank | 47_benchmark_policy_doris | set_intersect | medium | 0 | 32.2237 | 40.293 | True | PASS |
