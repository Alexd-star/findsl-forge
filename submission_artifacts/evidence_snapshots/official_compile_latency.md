# 正式编译器延迟基准

- Git HEAD：`dd61d10a39adfaf720720254df0a9bb557255b25`
- Catalog snapshot：`20d512c6ad746c913d456fdacfa0e79d7bf5d3a13cfbda457fb78245f0ffefc0`
- 用例/样本：`48/144`
- P50/P95/P99：`16.0269/47.7078/54.4491` ms
- P95 目标：`<50.0` ms
- 门禁：`PASS`

| Case | 函数族 | 计划族 | 策略 | P50 | P95 | P99 | Max | 状态 |
|---|---|---|---|---:|---:|---:|---:|---|
| CORR-ADAPTIVE-AGGREGATE-002 | indicator | prefix_long_horizon | volume_prefix_aggregate | 7.9933 | 8.4747 | 8.4747 | 8.4747 | PASS |
| CORR-PHASE10-JOIN-DORIS-001-BASIC-EXT-LATEST | indicator | 10_join_doris | stable_key_join | 12.0133 | 14.2414 | 14.2414 | 14.2414 | PASS |
| CORR-PHASE10-JOIN-DORIS-002-BASIC-SECURITY-LATEST | indicator | 10_join_doris | stable_key_join | 11.3209 | 11.9084 | 11.9084 | 11.9084 | PASS |
| CORR-PHASE11-DATE-DORIS-001-CHINESE-YEAR-2024 | indicator | 11_date_doris | direct_column | 12.7589 | 17.8744 | 17.8744 | 17.8744 | PASS |
| CORR-PHASE12-SESSION-DORIS-001-RECENT-5-SESSIONS | indicator | 12_session_doris | direct_column | 13.7124 | 13.9602 | 13.9602 | 13.9602 | PASS |
| CORR-PHASE13-MARKET-DORIS-001-STAR-MARKET | indicator | 13_market_doris | direct_column | 13.2566 | 13.6579 | 13.6579 | 13.6579 | PASS |
| CORR-PHASE14-AGGREGATE-DORIS-001-SUM-VOLUME-5 | indicator | 14_aggregate_doris | grouped_aggregate | 12.0152 | 13.4146 | 13.4146 | 13.4146 | PASS |
| CORR-PHASE15-UNIVERSE-DORIS-001-FULL-LATEST-UNIVERSE | indicator | 15_universe_doris | direct_column | 6.2595 | 9.7063 | 9.7063 | 9.7063 | PASS |
| CORR-PHASE16-COMPOSITE-DORIS-001-LATEST-EQUALS-MIN-100-SESSIONS | indicator | 16_composite_doris | composite_grouped_aggregate | 17.4446 | 18.2208 | 18.2208 | 18.2208 | PASS |
| CORR-PHASE17-RANK-DORIS-001-DIRECT-TOP-10 | rank | 17_rank_doris | direct_column | 7.512 | 8.6501 | 8.6501 | 8.6501 | PASS |
| CORR-PHASE17-RANK-DORIS-002-DIRECT-TOP-10-PERCENT | rank | 17_rank_doris | direct_column | 12.7091 | 21.2121 | 21.2121 | 21.2121 | PASS |
| CORR-PHASE17-RANK-DORIS-003-AGGREGATE-AVG-TOP-10 | rank | 17_rank_doris | aggregate_rank | 10.4501 | 15.3841 | 15.3841 | 15.3841 | PASS |
| CORR-PHASE18-DYNAMIC-DATE-DORIS-001-CURRENT-MONTH | indicator | 18_dynamic_date_doris | direct_column | 14.672 | 14.7989 | 14.7989 | 14.7989 | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | 19.1413 | 22.945 | 22.945 | 22.945 | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-005-GLOBAL-QUERYDATA-AGGREGATE | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | 21.7306 | 26.3489 | 26.3489 | 26.3489 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE | cross_above | 20_mapping_event_doris | crossing_window | 11.1083 | 15.5917 | 15.5917 | 15.5917 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS | record_high | 20_mapping_event_doris | crossing_window | 14.3955 | 16.1932 | 16.1932 | 16.1932 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY | record_low | 20_mapping_event_doris | crossing_window | 11.5645 | 12.8439 | 12.8439 | 12.8439 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN | close_together | 20_mapping_event_doris | crossing_window | 8.9505 | 10.8198 | 10.8198 | 10.8198 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN | reset | 20_mapping_event_doris | crossing_window | 14.6411 | 16.0269 | 16.0269 | 16.0269 | PASS |
| CORR-PHASE21-AGGREGATE-RANK-DORIS-001-CONFIGURED-RELATIVE-APPROXIMATIO | indicator | 21_aggregate_rank_doris | controlled_expression | 15.9945 | 25.3234 | 25.3234 | 25.3234 | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-001-NAMED-RANK-ARITHMETIC | rank | named_rank_expression | named_rank_expression | 19.5525 | 26.8261 | 26.8261 | 26.8261 | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-006-PARENTHESIZED-STAGE-UNION | indicator,rank | set_union | set_union | 37.7486 | 40.9749 | 40.9749 | 40.9749 | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-001-NOT-EVERY-RECENT-FIVE | indicator | direct_column | direct_column | 13.6093 | 16.3224 | 16.3224 | 16.3224 | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-003-MULTI-RESOURCE-TEMPORAL-JOIN | indicator | stable_temporal_join | stable_temporal_join | 23.4631 | 36.0293 | 36.0293 | 36.0293 | PASS |
| CORR-PHASE24-PERIOD-SCALAR-DORIS-003-PERIOD-QUERYDATA-CROSS-SCALAR | indicator,queryData | composite_grouped_aggregate | composite_grouped_aggregate | 22.5856 | 23.7214 | 23.7214 | 23.7214 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-001-PERIOD-RECORD-HIGH-AND-GROUPED-A | indicator,record_high | event_candidate_intersect | event_candidate_intersect | 43.2373 | 48.6988 | 48.6988 | 48.6988 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-002-PERIOD-EVENT-ABSENCE-USES-DECIDA | cross_down,indicator | event_candidate_intersect | event_candidate_intersect | 26.8451 | 27.9056 | 27.9056 | 27.9056 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-004-EVENT-UNION-AND-MULTI-GROWTH-REL | cross_above,cross_down,indicator | event_candidate_intersect | event_candidate_intersect | 47.7078 | 48.2837 | 48.2837 | 48.2837 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-005-DIFFERENT-EVENT-AND-INDICATOR-DA | indicator,record_high | event_candidate_intersect | event_candidate_intersect | 19.8979 | 26.8134 | 26.8134 | 26.8134 | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-001-FIXED-YEAR-FOLLOWING-RANGE | indicator | grouped_aggregate | grouped_aggregate | 13.4077 | 15.1756 | 15.1756 | 15.1756 | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-005-FRACTIONAL-YEAR-TO-SIX-MONTH-BUC | indicator | temporal_grouped_aggregate | temporal_grouped_aggregate | 27.1684 | 60.9139 | 60.9139 | 60.9139 | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE | golden_cross | temporal_event_projection | temporal_event_projection | 16.8059 | 18.4555 | 18.4555 | 18.4555 | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-002-MONTHLY-CROSSING-BUCKET | golden_cross | temporal_event_projection | temporal_event_projection | 17.9337 | 30.6016 | 30.6016 | 30.6016 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-002-PRICE-DOES-NOT-CROSS-BELOW-MA60 | cross_down | crossing_window_absence | crossing_window_absence | 19.1992 | 19.2731 | 19.2731 | 19.2731 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-003-PRICE-AT-FIVE-SESSION-LOW | record_low | crossing_window | crossing_window | 8.4544 | 18.5727 | 18.5727 | 18.5727 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-004-PRICE-IN-LOW-HISTORICAL-QUARTILE | position | crossing_window | crossing_window | 17.6821 | 18.6023 | 18.6023 | 18.6023 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-005-PRICE-CLOSE-TO-MA20 | close_together | crossing_window | crossing_window | 15.6903 | 16.5893 | 16.5893 | 16.5893 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-006-PRICE-RESETS-TO-MA5 | reset | crossing_window | crossing_window | 13.4537 | 13.7977 | 13.7977 | 13.7977 | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-002-REPEATED-TWENTY-SESSION-LOW | record_low | temporal_event_projection | temporal_event_projection | 13.8301 | 18.2204 | 18.2204 | 18.2204 | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-003-THREE-SESSION-PRICE-MA5-CONVERGE | close_together | temporal_event_projection | temporal_event_projection | 30.1735 | 33.8544 | 33.8544 | 33.8544 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-004-SUPPORT-RESET-AND-PRESSURE-CROSS | cross_above,cross_down,reset | set_intersect | set_intersect | 43.5166 | 54.4491 | 54.4491 | 54.4491 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-005-UNSEALED-LIMIT-EVENT | indicator | controlled_expression | controlled_expression | 14.7254 | 15.106 | 15.106 | 15.106 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-006-HALF-YEAR-HISTORICAL-LOW | position | crossing_window | crossing_window | 18.8688 | 24.1553 | 24.1553 | 24.1553 | PASS |
| CORR-PHASE31-FINAL-GROUNDED-DORIS-002-EVENT-CANDIDATE-THEN-RANK | indicator,position,rank | stage_rank | stage_rank | 50.6816 | 53.9528 | 53.9528 | 53.9528 | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-002-CSI300-SSE-MAIN-BOARD-INDUSTRY-A | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | 46.488 | 49.8689 | 49.8689 | 49.8689 | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | 22.3002 | 25.6368 | 25.6368 | 25.6368 | PASS |
| CORR-PHASE47-BENCHMARK-POLICY-DORIS-001-AI-TOP1-NOT-OUTPERFORM-BENCHMARK | indicator,queryData,rank | 47_benchmark_policy_doris | set_intersect | 40.9924 | 47.2068 | 47.2068 | 47.2068 | PASS |
