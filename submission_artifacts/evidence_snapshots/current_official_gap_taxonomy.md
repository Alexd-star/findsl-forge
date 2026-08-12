# 官方语料缺口能力聚类

> 本报告按能力族统计，不把 Excel 行当作独立开发任务。

## 总体分类

| 分类 | 行数 | 处理原则 |
|---|---:|---|
| 已通过 | 1083 | 保持回归，不重复开发 |
| 数据不可用 | 1720 | 通过版本化数据目录或结构化拒绝处理 |
| 非法输入 | 2466 | 严格模式继续拒绝 |
| 能力缺口 | 530 | 按通用规则聚类开发 |

旧成功集迁移缺口：**53 条**；错误码：PHYSICAL_SCOPE_DATA_UNAVAILABLE。

## 能力聚类

| 错误码 | 分类 | 行数 | 涉及函数族 | 代表行 |
|---|---|---:|---|---|
| OFFICIAL_TYPE_ERROR | invalid_input | 2459 | belong_industry, close_together, cross_above, cross_down, golden_cross, indicator, position, queryData, rank, record_high, record_low, reset | 3, 5, 9, 10, 15 |
| DOMAIN_DATA_UNAVAILABLE | data_unavailable | 1504 | belong_industry, close_together, cross_above, cross_down, golden_cross, indicator, position, queryData, rank, record_high, record_low, reset | 2, 4, 6, 7, 8 |
| PHYSICAL_CONSTRAINT_UNSUPPORTED | capability_gap | 282 | belong_industry, close_together, cross_above, cross_down, indicator, position, queryData, rank, record_high, record_low | 18, 39, 296, 299, 310 |
| PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED | capability_gap | 239 | belong_industry, cross_above, cross_down, golden_cross, indicator, position, queryData, rank, record_high, record_low, reset | 112, 183, 196, 237, 271 |
| PHYSICAL_SCOPE_DATA_UNAVAILABLE | data_unavailable | 119 | belong_industry, close_together, cross_above, cross_down, indicator, queryData, rank, record_high, record_low, reset | 65, 83, 177, 204, 208 |
| PHYSICAL_MARKET_DATA_UNAVAILABLE | data_unavailable | 96 | belong_industry, close_together, cross_above, cross_down, indicator, position, queryData, rank, record_high, reset | 53, 242, 278, 285, 560 |
| OFFICIAL_ANTLR_LEX_ERROR | invalid_input | 5 | 无 | 2122, 2194, 2466, 5328, 5753 |
| PHYSICAL_EVENT_PERIOD_UNSUPPORTED | capability_gap | 3 | indicator, position | 3929, 3976, 5504 |
| OFFICIAL_ANTLR_PARSE_ERROR | invalid_input | 2 | 无 | 3785, 5521 |
| PHYSICAL_PLAN_UNAVAILABLE | capability_gap | 2 | indicator, rank | 2143, 4050 |
| TEMPORAL_SCOPE_MISMATCH | capability_gap | 2 | indicator | 2439, 2509 |
| DOMAIN_DATE_INVALID | capability_gap | 1 | indicator | 3639 |
| PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE | data_unavailable | 1 | indicator, queryData | 307 |
| PHYSICAL_RANK_EXPRESSION_UNSUPPORTED | capability_gap | 1 | indicator, rank | 1198 |

## 语义根因子类

| 根因 | 分类 | 行数 | 错误码 | 代表行 |
|---|---|---:|---|---|
| invalid_dsl_or_type | invalid_input | 2466 | OFFICIAL_ANTLR_LEX_ERROR, OFFICIAL_ANTLR_PARSE_ERROR, OFFICIAL_TYPE_ERROR | 3, 5, 9, 10, 15 |
| declared_data_unavailable | data_unavailable | 1720 | DOMAIN_DATA_UNAVAILABLE, PHYSICAL_MARKET_DATA_UNAVAILABLE, PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE, PHYSICAL_SCOPE_DATA_UNAVAILABLE | 2, 4, 6, 7, 8 |
| other_date_algebra | capability_gap | 165 | PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED | 196, 271, 342, 361, 370 |
| unsupported_asset_domain | data_unavailable | 143 | PHYSICAL_CONSTRAINT_UNSUPPORTED | 18, 39, 296, 299, 310 |
| physical_constraint_unsupported | capability_gap | 139 | PHYSICAL_CONSTRAINT_UNSUPPORTED | 365, 563, 778, 828, 833 |
| intraday_data_domain | data_unavailable | 27 | PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED | 237, 505, 1006, 1228, 1248 |
| fundamental_reporting_calendar | data_unavailable | 24 | PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED | 308, 320, 529, 658, 752 |
| ambiguous_recent_date | invalid_input | 23 | PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED | 112, 183, 298, 413, 1017 |
| physical_event_period_unsupported | capability_gap | 3 | PHYSICAL_EVENT_PERIOD_UNSUPPORTED | 3929, 3976, 5504 |
| physical_plan_unavailable | capability_gap | 2 | PHYSICAL_PLAN_UNAVAILABLE | 2143, 4050 |
| temporal_scope_mismatch | capability_gap | 2 | TEMPORAL_SCOPE_MISMATCH | 2439, 2509 |
| domain_date_invalid | capability_gap | 1 | DOMAIN_DATE_INVALID | 3639 |
| physical_rank_expression_unsupported | capability_gap | 1 | PHYSICAL_RANK_EXPRESSION_UNSUPPORTED | 1198 |

## 开发门禁

每个能力族必须先确定根因层级，再实现通用规则，并批量回归全部匹配语料。禁止根据完整 DSL 文本或单个 Excel 行添加生产分支。
