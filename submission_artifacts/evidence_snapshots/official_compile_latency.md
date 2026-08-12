# 正式编译器延迟基准

- Git HEAD：`dd61d10a39adfaf720720254df0a9bb557255b25`
- Catalog snapshot：`9410de3a8f759f0c5e486d8db61f01da446aa428d414a8b64e6b87a3afa79783`
- 用例/样本：`48/1440`
- P50/P95/P99：`10.5165/29.7163/42.3681` ms
- P95 目标：`<50.0` ms
- 门禁：`PASS`

| Case | 函数族 | 计划族 | 策略 | P50 | P95 | P99 | Max | 状态 |
|---|---|---|---|---:|---:|---:|---:|---|
| CORR-ADAPTIVE-AGGREGATE-002 | indicator | prefix_long_horizon | volume_prefix_aggregate | 5.9057 | 6.6428 | 6.8678 | 6.8678 | PASS |
| CORR-PHASE10-JOIN-DORIS-001-BASIC-EXT-LATEST | indicator | 10_join_doris | stable_key_join | 10.7367 | 14.7843 | 22.175 | 22.175 | PASS |
| CORR-PHASE10-JOIN-DORIS-002-BASIC-SECURITY-LATEST | indicator | 10_join_doris | stable_key_join | 9.3399 | 11.3266 | 11.4237 | 11.4237 | PASS |
| CORR-PHASE11-DATE-DORIS-001-CHINESE-YEAR-2024 | indicator | 11_date_doris | direct_column | 6.5238 | 7.5214 | 8.6533 | 8.6533 | PASS |
| CORR-PHASE12-SESSION-DORIS-001-RECENT-5-SESSIONS | indicator | 12_session_doris | direct_column | 6.4813 | 7.664 | 8.1642 | 8.1642 | PASS |
| CORR-PHASE13-MARKET-DORIS-001-STAR-MARKET | indicator | 13_market_doris | direct_column | 7.1983 | 8.457 | 8.8307 | 8.8307 | PASS |
| CORR-PHASE14-AGGREGATE-DORIS-001-SUM-VOLUME-5 | indicator | 14_aggregate_doris | grouped_aggregate | 9.4956 | 11.0851 | 12.9556 | 12.9556 | PASS |
| CORR-PHASE15-UNIVERSE-DORIS-001-FULL-LATEST-UNIVERSE | indicator | 15_universe_doris | direct_column | 6.7146 | 8.6865 | 9.139 | 9.139 | PASS |
| CORR-PHASE16-COMPOSITE-DORIS-001-LATEST-EQUALS-MIN-100-SESSIONS | indicator | 16_composite_doris | composite_grouped_aggregate | 10.6873 | 15.4454 | 23.4598 | 23.4598 | PASS |
| CORR-PHASE17-RANK-DORIS-001-DIRECT-TOP-10 | rank | 17_rank_doris | direct_column | 8.9058 | 14.432 | 15.4236 | 15.4236 | PASS |
| CORR-PHASE17-RANK-DORIS-002-DIRECT-TOP-10-PERCENT | rank | 17_rank_doris | direct_column | 7.2512 | 12.565 | 15.1247 | 15.1247 | PASS |
| CORR-PHASE17-RANK-DORIS-003-AGGREGATE-AVG-TOP-10 | rank | 17_rank_doris | aggregate_rank | 9.5934 | 12.4637 | 13.6788 | 13.6788 | PASS |
| CORR-PHASE18-DYNAMIC-DATE-DORIS-001-CURRENT-MONTH | indicator | 18_dynamic_date_doris | direct_column | 6.7754 | 7.8276 | 10.6921 | 10.6921 | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | 10.3372 | 11.5059 | 21.7904 | 21.7904 | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-005-GLOBAL-QUERYDATA-AGGREGATE | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | 14.3428 | 20.0559 | 20.6648 | 20.6648 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE | cross_above | 20_mapping_event_doris | crossing_window | 8.8468 | 14.5151 | 14.6303 | 14.6303 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS | record_high | 20_mapping_event_doris | crossing_window | 8.0076 | 12.9675 | 19.1682 | 19.1682 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY | record_low | 20_mapping_event_doris | crossing_window | 7.1762 | 9.8433 | 10.5285 | 10.5285 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN | close_together | 20_mapping_event_doris | crossing_window | 9.0151 | 13.5523 | 16.5358 | 16.5358 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN | reset | 20_mapping_event_doris | crossing_window | 9.058 | 11.971 | 12.3119 | 12.3119 | PASS |
| CORR-PHASE21-AGGREGATE-RANK-DORIS-001-CONFIGURED-RELATIVE-APPROXIMATIO | indicator | 21_aggregate_rank_doris | controlled_expression | 6.48 | 7.0833 | 7.5513 | 7.5513 | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-001-NAMED-RANK-ARITHMETIC | rank | named_rank_expression | named_rank_expression | 13.1199 | 16.0518 | 24.1904 | 24.1904 | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-006-PARENTHESIZED-STAGE-UNION | indicator,rank | set_union | set_union | 28.6239 | 42.0819 | 48.4076 | 48.4076 | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-001-NOT-EVERY-RECENT-FIVE | indicator | direct_column | direct_column | 9.2183 | 10.0724 | 22.7771 | 22.7771 | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-003-MULTI-RESOURCE-TEMPORAL-JOIN | indicator | stable_temporal_join | stable_temporal_join | 16.326 | 25.8293 | 29.4939 | 29.4939 | PASS |
| CORR-PHASE24-PERIOD-SCALAR-DORIS-003-PERIOD-QUERYDATA-CROSS-SCALAR | indicator,queryData | composite_grouped_aggregate | composite_grouped_aggregate | 15.4168 | 19.3458 | 27.747 | 27.747 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-001-PERIOD-RECORD-HIGH-AND-GROUPED-A | indicator,record_high | event_candidate_intersect | event_candidate_intersect | 15.8074 | 24.84 | 29.1092 | 29.1092 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-002-PERIOD-EVENT-ABSENCE-USES-DECIDA | cross_down,indicator | event_candidate_intersect | event_candidate_intersect | 18.9381 | 29.9071 | 33.6526 | 33.6526 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-004-EVENT-UNION-AND-MULTI-GROWTH-REL | cross_above,cross_down,indicator | event_candidate_intersect | event_candidate_intersect | 29.6244 | 56.3838 | 57.3387 | 57.3387 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-005-DIFFERENT-EVENT-AND-INDICATOR-DA | indicator,record_high | event_candidate_intersect | event_candidate_intersect | 13.239 | 14.534 | 27.5234 | 27.5234 | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-001-FIXED-YEAR-FOLLOWING-RANGE | indicator | grouped_aggregate | grouped_aggregate | 7.4534 | 8.6428 | 9.6048 | 9.6048 | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-005-FRACTIONAL-YEAR-TO-SIX-MONTH-BUC | indicator | temporal_grouped_aggregate | temporal_grouped_aggregate | 15.6 | 29.7867 | 31.5837 | 31.5837 | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE | golden_cross | temporal_event_projection | temporal_event_projection | 12.1342 | 16.1351 | 17.7262 | 17.7262 | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-002-MONTHLY-CROSSING-BUCKET | golden_cross | temporal_event_projection | temporal_event_projection | 14.1953 | 20.6688 | 44.2793 | 44.2793 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-002-PRICE-DOES-NOT-CROSS-BELOW-MA60 | cross_down | crossing_window_absence | crossing_window_absence | 10.6065 | 11.9927 | 27.3719 | 27.3719 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-003-PRICE-AT-FIVE-SESSION-LOW | record_low | crossing_window | crossing_window | 6.8643 | 7.8319 | 9.5633 | 9.5633 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-004-PRICE-IN-LOW-HISTORICAL-QUARTILE | position | crossing_window | crossing_window | 10.5774 | 12.6448 | 23.503 | 23.503 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-005-PRICE-CLOSE-TO-MA20 | close_together | crossing_window | crossing_window | 8.1075 | 8.9689 | 9.6009 | 9.6009 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-006-PRICE-RESETS-TO-MA5 | reset | crossing_window | crossing_window | 8.4092 | 9.379 | 10.2017 | 10.2017 | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-002-REPEATED-TWENTY-SESSION-LOW | record_low | temporal_event_projection | temporal_event_projection | 10.9781 | 13.2943 | 25.4021 | 25.4021 | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-003-THREE-SESSION-PRICE-MA5-CONVERGE | close_together | temporal_event_projection | temporal_event_projection | 16.7227 | 20.7408 | 32.8538 | 32.8538 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-004-SUPPORT-RESET-AND-PRESSURE-CROSS | cross_above,cross_down,reset | set_intersect | set_intersect | 25.0313 | 39.5885 | 41.3545 | 41.3545 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-005-UNSEALED-LIMIT-EVENT | indicator | controlled_expression | controlled_expression | 7.7748 | 9.0027 | 9.1508 | 9.1508 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-006-HALF-YEAR-HISTORICAL-LOW | position | crossing_window | crossing_window | 10.8307 | 12.2507 | 25.8114 | 25.8114 | PASS |
| CORR-PHASE31-FINAL-GROUNDED-DORIS-002-EVENT-CANDIDATE-THEN-RANK | indicator,position,rank | stage_rank | stage_rank | 32.4249 | 52.3032 | 66.0799 | 66.0799 | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-002-CSI300-SSE-MAIN-BOARD-INDUSTRY-A | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | 24.7449 | 42.3681 | 47.0583 | 47.0583 | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | 15.4194 | 23.3534 | 32.3224 | 32.3224 | PASS |
| CORR-PHASE47-BENCHMARK-POLICY-DORIS-001-AI-TOP1-NOT-OUTPERFORM-BENCHMARK | indicator,queryData,rank | 47_benchmark_policy_doris | set_intersect | 21.8247 | 33.4547 | 40.7396 | 40.7396 | PASS |
