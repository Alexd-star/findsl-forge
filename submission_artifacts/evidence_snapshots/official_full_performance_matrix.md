# 官方真实数据分层性能矩阵

- Git HEAD：`414a9803964a61ffa1876b9d1bbda0fba0e6a298`
- Catalog snapshot：`0220ac16d8cdf779da910d7289bb979da84ea1328198ed7b7029bd09e6f1b636`
- 用例：`48`
- 全部匹配独立 reference：`True`
- 全部 P95 <= 10s：`True`
- 最大 P95：`2945.0978` ms

| Case | 函数族 | 计划族 | 策略 | 负载 | Rows | Compile ms | P95 ms | 10s | 状态 |
|---|---|---|---|---|---:|---:|---:|---|---|
| CORR-ADAPTIVE-AGGREGATE-002 | indicator | prefix_long_horizon | volume_prefix_aggregate | heavy | 5614 | 41.6385 | 111.5599 | True | PASS |
| CORR-PHASE10-JOIN-DORIS-001-BASIC-EXT-LATEST | indicator | 10_join_doris | stable_key_join | medium | 2247 | 43.7723 | 46.6812 | True | PASS |
| CORR-PHASE10-JOIN-DORIS-002-BASIC-SECURITY-LATEST | indicator | 10_join_doris | stable_key_join | medium | 5573 | 42.4192 | 213.1703 | True | PASS |
| CORR-PHASE11-DATE-DORIS-001-CHINESE-YEAR-2024 | indicator | 11_date_doris | direct_column | medium | 16734 | 36.953 | 80.2058 | True | PASS |
| CORR-PHASE12-SESSION-DORIS-001-RECENT-5-SESSIONS | indicator | 12_session_doris | direct_column | medium | 467 | 31.7196 | 42.9674 | True | PASS |
| CORR-PHASE13-MARKET-DORIS-001-STAR-MARKET | indicator | 13_market_doris | direct_column | medium | 606 | 36.4756 | 41.3022 | True | PASS |
| CORR-PHASE14-AGGREGATE-DORIS-001-SUM-VOLUME-5 | indicator | 14_aggregate_doris | grouped_aggregate | medium | 574 | 39.8344 | 41.3633 | True | PASS |
| CORR-PHASE15-UNIVERSE-DORIS-001-FULL-LATEST-UNIVERSE | indicator | 15_universe_doris | direct_column | medium | 5614 | 34.6187 | 114.9083 | True | PASS |
| CORR-PHASE16-COMPOSITE-DORIS-001-LATEST-EQUALS-MIN-100-SESSIONS | indicator | 16_composite_doris | composite_grouped_aggregate | medium | 72 | 41.6539 | 44.1342 | True | PASS |
| CORR-PHASE17-RANK-DORIS-001-DIRECT-TOP-10 | rank | 17_rank_doris | direct_column | medium | 10 | 38.581 | 40.3204 | True | PASS |
| CORR-PHASE17-RANK-DORIS-002-DIRECT-TOP-10-PERCENT | rank | 17_rank_doris | direct_column | medium | 562 | 32.5681 | 45.239 | True | PASS |
| CORR-PHASE17-RANK-DORIS-003-AGGREGATE-AVG-TOP-10 | rank | 17_rank_doris | aggregate_rank | medium | 10 | 35.6602 | 35.2819 | True | PASS |
| CORR-PHASE18-DYNAMIC-DATE-DORIS-001-CURRENT-MONTH | indicator | 18_dynamic_date_doris | direct_column | medium | 867 | 36.7666 | 39.2221 | True | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | medium | 1896 | 38.0935 | 44.3557 | True | PASS |
| CORR-PHASE19-SECURITY-SCOPE-DORIS-005-GLOBAL-QUERYDATA-AGGREGATE | indicator,queryData | 19_security_scope_doris | composite_grouped_aggregate | medium | 1872 | 40.2246 | 39.8266 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE | cross_above | 20_mapping_event_doris | crossing_window | medium | 887 | 32.3825 | 479.2861 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS | record_high | 20_mapping_event_doris | crossing_window | medium | 219 | 45.4046 | 40.6687 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY | record_low | 20_mapping_event_doris | crossing_window | medium | 4 | 38.0369 | 40.2412 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN | close_together | 20_mapping_event_doris | crossing_window | medium | 3598 | 38.11 | 883.8739 | True | PASS |
| CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN | reset | 20_mapping_event_doris | crossing_window | medium | 1449 | 48.6138 | 46.1158 | True | PASS |
| CORR-PHASE21-AGGREGATE-RANK-DORIS-001-CONFIGURED-RELATIVE-APPROXIMATIO | indicator | 21_aggregate_rank_doris | controlled_expression | medium | 38 | 35.4672 | 37.0902 | True | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-001-NAMED-RANK-ARITHMETIC | rank | named_rank_expression | named_rank_expression | medium | 2927 | 56.4531 | 39.7498 | True | PASS |
| CORR-PHASE22-STAGE-RANK-DORIS-006-PARENTHESIZED-STAGE-UNION | indicator,rank | set_union | set_union | medium | 1 | 84.1179 | 42.0511 | True | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-001-NOT-EVERY-RECENT-FIVE | indicator | direct_column | direct_column | light | 48 | 51.7107 | 46.5661 | True | PASS |
| CORR-PHASE23-RELATIONAL-DORIS-003-MULTI-RESOURCE-TEMPORAL-JOIN | indicator | stable_temporal_join | stable_temporal_join | heavy | 2929 | 60.5305 | 44.0742 | True | PASS |
| CORR-PHASE24-PERIOD-SCALAR-DORIS-003-PERIOD-QUERYDATA-CROSS-SCALAR | indicator,queryData | composite_grouped_aggregate | composite_grouped_aggregate | heavy | 5115 | 51.0757 | 259.4085 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-001-PERIOD-RECORD-HIGH-AND-GROUPED-A | indicator,record_high | event_candidate_intersect | event_candidate_intersect | heavy | 1196 | 48.5445 | 44.3302 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-002-PERIOD-EVENT-ABSENCE-USES-DECIDA | cross_down,indicator | event_candidate_intersect | event_candidate_intersect | heavy | 4453 | 59.6111 | 2295.9372 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-004-EVENT-UNION-AND-MULTI-GROWTH-REL | cross_above,cross_down,indicator | event_candidate_intersect | event_candidate_intersect | heavy | 442 | 74.5386 | 42.5565 | True | PASS |
| CORR-PHASE25-EVENT-CANDIDATE-DORIS-005-DIFFERENT-EVENT-AND-INDICATOR-DA | indicator,record_high | event_candidate_intersect | event_candidate_intersect | heavy | 299 | 38.8807 | 65.1026 | True | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-001-FIXED-YEAR-FOLLOWING-RANGE | indicator | grouped_aggregate | grouped_aggregate | medium | 2933 | 30.5008 | 85.089 | True | PASS |
| CORR-PHASE26-DATE-LIMIT-DORIS-005-FRACTIONAL-YEAR-TO-SIX-MONTH-BUC | indicator | temporal_grouped_aggregate | temporal_grouped_aggregate | heavy | 5537 | 48.3325 | 373.3977 | True | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE | golden_cross | temporal_event_projection | temporal_event_projection | heavy | 4870 | 56.47 | 2200.6251 | True | PASS |
| CORR-PHASE27-EVENT-SEMANTICS-DORIS-002-MONTHLY-CROSSING-BUCKET | golden_cross | temporal_event_projection | temporal_event_projection | heavy | 1659 | 55.2335 | 46.1852 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-002-PRICE-DOES-NOT-CROSS-BELOW-MA60 | cross_down | crossing_window_absence | crossing_window_absence | heavy | 5547 | 43.7487 | 2945.0978 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-003-PRICE-AT-FIVE-SESSION-LOW | record_low | crossing_window | crossing_window | heavy | 919 | 33.8898 | 40.266 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-004-PRICE-IN-LOW-HISTORICAL-QUARTILE | position | crossing_window | crossing_window | heavy | 797 | 37.9903 | 39.4956 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-005-PRICE-CLOSE-TO-MA20 | close_together | crossing_window | crossing_window | heavy | 3018 | 31.6917 | 816.5314 | True | PASS |
| CORR-PHASE28-DEFAULT-PRICE-DORIS-006-PRICE-RESETS-TO-MA5 | reset | crossing_window | crossing_window | heavy | 2855 | 39.8548 | 40.2065 | True | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-002-REPEATED-TWENTY-SESSION-LOW | record_low | temporal_event_projection | temporal_event_projection | heavy | 4551 | 40.2137 | 1002.6126 | True | PASS |
| CORR-PHASE29-EVENT-PROJECTION-DORIS-003-THREE-SESSION-PRICE-MA5-CONVERGE | close_together | temporal_event_projection | temporal_event_projection | heavy | 5444 | 55.9408 | 1121.3363 | True | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-004-SUPPORT-RESET-AND-PRESSURE-CROSS | cross_above,cross_down,reset | set_intersect | set_intersect | medium | 85 | 73.9058 | 38.5527 | True | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-005-UNSEALED-LIMIT-EVENT | indicator | controlled_expression | controlled_expression | light | 35 | 36.5618 | 39.2722 | True | PASS |
| CORR-PHASE30-GROUNDED-EVENT-DORIS-006-HALF-YEAR-HISTORICAL-LOW | position | crossing_window | crossing_window | heavy | 3513 | 60.8259 | 1034.1402 | True | PASS |
| CORR-PHASE31-FINAL-GROUNDED-DORIS-002-EVENT-CANDIDATE-THEN-RANK | indicator,position,rank | stage_rank | stage_rank | heavy | 2 | 88.6752 | 38.4878 | True | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-002-CSI300-SSE-MAIN-BOARD-INDUSTRY-A | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | medium | 61 | 74.5646 | 37.4847 | True | PASS |
| CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN | belong_industry,indicator | 46_derived_scope_doris | composite_grouped_aggregate | medium | 582 | 48.0818 | 39.6769 | True | PASS |
| CORR-PHASE47-BENCHMARK-POLICY-DORIS-001-AI-TOP1-NOT-OUTPERFORM-BENCHMARK | indicator,queryData,rank | 47_benchmark_policy_doris | set_intersect | medium | 0 | 66.5356 | 35.1411 | True | PASS |
