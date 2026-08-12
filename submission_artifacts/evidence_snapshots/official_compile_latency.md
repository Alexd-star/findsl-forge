# 正式编译器延迟基准

- Git HEAD：`a531f1c42169199bc958ffcbafbf122f0f4928d7`
- Catalog snapshot：`9198d534b9430211f5d24cdf4700f95f761e9e077e5e1cf6bb03d8282b6c1dbd`
- 用例/样本：`48/1440`
- P50/P95/P99：`10.0795/29.4199/42.2271` ms
- P95 目标：`<50.0` ms
- 门禁：`PASS`

| Case | 函数族 | 计划族 | 策略 | P50 | P95 | P99 | Max | 状态 |
|---|---|---|---|---:|---:|---:|---:|---|
| CORR-ADAPTIVE-AGGREGATE-002 | indicator | prefix_long_horizon | volume_prefix_aggregate | 5.5215 | 7.7064 | 8.2088 | 8.2088 | PASS |
| CORR-PHASE10-JOIN-DORIS-001-BASIC-EXT-LATEST | indicator | 10_join_doris | stable_key_join | 9.5221 | 10.7278 | 11.6205 | 11.6205 | PASS |
| CORR-PHASE10-JOIN-DORIS-002-BASIC-SECURITY-LATEST | indicator | 10_join_doris | stable_key_join | 9.0297 | 10.6435 | 10.7613 | 10.7613 | PASS |
| CORR-PHASE11-DATE-DORIS-001-CHINESE-YEAR-2024 | indicator | 11_date_doris | direct_column | 6.3794 | 8.6206 | 9.3575 | 9.3575 | PASS |
| CORR-PHASE12-SESSION-DORIS-001-RECENT-5-SESSIONS | indicator | 12_session_doris | direct_column | 6.8613 | 8.3048 | 8.6534 | 8.6534 | PASS |
| CORR-PHASE13-MARKET-DORIS-001-STAR-MARKET | indicator | 13_market_doris | direct_column | 6.7448 | 7.8208 | 8.1001 | 8.1001 | PASS |
| CORR-PHASE14-AGGREGATE-DORIS-001-SUM-VOLUME-5 | indicator | 14_aggregate_doris | grouped_aggregate | 8.8012 | 9.6407 | 9.7946 | 9.7946 | PASS |
| CORR-PHASE15-UNIVERSE-DORIS-001-FULL-LATEST-UNIVERSE | indicator | 15_universe_doris | direct_column | 5.5582 | 6.6182 | 7.6666 | 7.6666 | PASS |
| CORR-PHASE16-COMPOSITE-DORIS-001-LATEST-EQUALS-MIN-100-SESSIONS | indicator | 16_composite_doris | composite_grouped_aggregate | 10.1921 | 11.9747 | 12.0451 | 12.0451 | PASS |
| CORR-PHASE17-RANK-DORIS-001-DIRECT-TOP-10 | rank | 17_rank_doris | direct_column | 6.8964 | 8.4881 | 8.9471 | 8.9471 | PASS |
| CORR-PHASE17-RANK-DORIS-002-DIRECT-TOP-10-PERCENT | rank | 17_rank_doris | direct_column | 6.8619 | 9.9744 | 18.3287 | 18.3287 | PASS |
| CORR-PHASE17-RANK-DORIS-003-AGGREGATE-AVG-TOP-10 | rank | 17_rank_doris | aggregate_rank | 9.425 | 10.6047 | 10.7606 | 10.7606 | PASS |
| CORR-PHASE18-DYNAMIC-DATE-DORIS-001-CURRENT-MONTH | indicator | 18_dynamic_date_doris | direct_column | 6.7012 | 9.4041 | 9.633 | 9.633 | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | 10.89 | 12.3965 | 17.3427 | 17.3427 | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-005-GLOBAL-QUERYDATA-AGGREGATE | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | 12.9498 | 15.7236 | 33.0837 | 33.0837 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE | cross_above | 20_mapping_event_doris | crossing_window | 7.7853 | 8.5856 | 9.1196 | 9.1196 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS | record_high | 20_mapping_event_doris | crossing_window | 7.4487 | 9.7323 | 10.2929 | 10.2929 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY | record_low | 20_mapping_event_doris | crossing_window | 7.1038 | 7.964 | 8.3842 | 8.3842 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN | close_together | 20_mapping_event_doris | crossing_window | 7.5249 | 8.9322 | 9.0544 | 9.0544 | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN | reset | 20_mapping_event_doris | crossing_window | 8.2095 | 10.8705 | 13.5081 | 13.5081 | PASS |
| CORR-PHASE21-AGGREGATE-RANK-DORIS-001-CONFIGURED-RELATIVE-APPROXIMATIO | indicator | 21_aggregate_rank_doris | controlled_expression | 6.2677 | 7.618 | 7.7351 | 7.7351 | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-001-NAMED-RANK-ARITHMETIC | rank | named_rank_expression | named_rank_expression | 12.9249 | 13.968 | 26.3554 | 26.3554 | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-006-PARENTHESIZED-STAGE-UNION | indicator,rank | set_union | set_union | 27.3175 | 38.3512 | 42.2271 | 42.2271 | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-001-NOT-EVERY-RECENT-FIVE | indicator | direct_column | direct_column | 9.2143 | 10.4925 | 11.1973 | 11.1973 | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-003-MULTI-RESOURCE-TEMPORAL-JOIN | indicator | stable_temporal_join | stable_temporal_join | 16.1417 | 17.2578 | 32.7958 | 32.7958 | PASS |
| CORR-PHASE24-PERIOD-SCALAR-DORIS-003-PERIOD-QUERYDATA-CROSS-SCALAR | indicator,queryData | composite_grouped_aggregate | composite_grouped_aggregate | 15.2734 | 24.358 | 32.8115 | 32.8115 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-001-PERIOD-RECORD-HIGH-AND-GROUPED-A | indicator,record_high | event_candidate_intersect | event_candidate_intersect | 15.9755 | 18.0772 | 31.9323 | 31.9323 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-002-PERIOD-EVENT-ABSENCE-USES-DECIDA | cross_down,indicator | event_candidate_intersect | event_candidate_intersect | 19.1245 | 33.2495 | 36.5681 | 36.5681 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-004-EVENT-UNION-AND-MULTI-GROWTH-REL | cross_above,cross_down,indicator | event_candidate_intersect | event_candidate_intersect | 29.5077 | 48.1426 | 48.5022 | 48.5022 | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-005-DIFFERENT-EVENT-AND-INDICATOR-DA | indicator,record_high | event_candidate_intersect | event_candidate_intersect | 13.0015 | 14.9409 | 30.3838 | 30.3838 | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-001-FIXED-YEAR-FOLLOWING-RANGE | indicator | grouped_aggregate | grouped_aggregate | 7.366 | 8.7534 | 11.2007 | 11.2007 | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-005-FRACTIONAL-YEAR-TO-SIX-MONTH-BUC | indicator | temporal_grouped_aggregate | temporal_grouped_aggregate | 16.1683 | 33.9914 | 34.4522 | 34.4522 | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE | golden_cross | temporal_event_projection | temporal_event_projection | 12.0659 | 14.3559 | 30.9442 | 30.9442 | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-002-MONTHLY-CROSSING-BUCKET | golden_cross | temporal_event_projection | temporal_event_projection | 14.257 | 16.4813 | 32.1284 | 32.1284 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-002-PRICE-DOES-NOT-CROSS-BELOW-MA60 | cross_down | crossing_window_absence | crossing_window_absence | 11.1943 | 13.8963 | 14.4511 | 14.4511 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-003-PRICE-AT-FIVE-SESSION-LOW | record_low | crossing_window | crossing_window | 6.7964 | 9.0873 | 9.6339 | 9.6339 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-004-PRICE-IN-LOW-HISTORICAL-QUARTILE | position | crossing_window | crossing_window | 10.8147 | 14.1677 | 27.8867 | 27.8867 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-005-PRICE-CLOSE-TO-MA20 | close_together | crossing_window | crossing_window | 8.7521 | 10.2533 | 11.2102 | 11.2102 | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-006-PRICE-RESETS-TO-MA5 | reset | crossing_window | crossing_window | 8.6432 | 9.9763 | 11.0309 | 11.0309 | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-002-REPEATED-TWENTY-SESSION-LOW | record_low | temporal_event_projection | temporal_event_projection | 10.8391 | 14.6385 | 29.0653 | 29.0653 | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-003-THREE-SESSION-PRICE-MA5-CONVERGE | close_together | temporal_event_projection | temporal_event_projection | 17.4677 | 20.7854 | 39.3765 | 39.3765 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-004-SUPPORT-RESET-AND-PRESSURE-CROSS | cross_above,cross_down,reset | set_intersect | set_intersect | 25.6733 | 42.2442 | 43.5245 | 43.5245 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-005-UNSEALED-LIMIT-EVENT | indicator | controlled_expression | controlled_expression | 7.8906 | 9.3464 | 9.5825 | 9.5825 | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-006-HALF-YEAR-HISTORICAL-LOW | position | crossing_window | crossing_window | 11.4413 | 15.721 | 28.7252 | 28.7252 | PASS |
| CORR-PHASE31-FINAL-GROUNDED-DORIS-002-EVENT-CANDIDATE-THEN-RANK | indicator,position,rank | stage_rank | stage_rank | 32.2661 | 55.7618 | 56.6933 | 56.6933 | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-002-CSI300-SSE-MAIN-BOARD-INDUSTRY-A | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | 25.8878 | 44.4224 | 46.248 | 46.248 | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | 15.2224 | 16.3587 | 17.322 | 17.322 | PASS |
| CORR-PHASE47-BENCHMARK-POLICY-DORIS-001-AI-TOP1-NOT-OUTPERFORM-BENCHMARK | indicator,queryData,rank | 47_benchmark_policy_doris | set_intersect | 19.7492 | 23.7326 | 35.7974 | 35.7974 | PASS |
