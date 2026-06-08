# Official-Style Coverage Suite

## Summary

- Suite passed: True
- Positive cases passed: 37/37
- Negative diagnostic cases passed: 37/37

## Positive Cases

| Case | Scenario | Passed | Equivalence | SQL rows | Reference rows | Missing evidence |
|---|---|---:|---:|---:|---:|---|
| A股连续3天主力净流入为正后按换手率排名 | staged_filter_rank | True | True | 2 | 2 | <none> |
| 今日收盘价创近3日新高 | max_window_breakout | True | True | 12 | 12 | <none> |
| 近10日存在放量信号 | exist_volume_above_ma | True | True | 11 | 11 | <none> |
| 成交量3日滚动求和走前缀表 | volume_prefix_sum | True | True | 7 | 7 | <none> |
| 主力净流入3日滚动求和走资金流前缀表 | money_flow_prefix_sum | True | True | 3 | 3 | <none> |
| 收盘价强于均线且成交量创新高 | compound_numeric_windows | True | True | 9 | 9 | <none> |
| B股近2日均量不低于80 | market_join_with_ma | True | True | 4 | 4 | <none> |
| A股高换手后按收盘价取每日前2 | filter_rank_top | True | True | 8 | 8 | <none> |
| A股存在资金流入后按低价取每日2只 | exist_rank_bottom | True | True | 9 | 9 | <none> |
| 收盘价加换手率大于12 | numeric_arithmetic | True | True | 9 | 9 | <none> |
| A股高换手率每日前50百分比 | rank_percent_cutoff | True | True | 5 | 5 | <none> |
| 日期区间下推后筛收盘价 | date_range_pushdown | True | True | 6 | 6 | <none> |
| 窗口查询日期上界安全裁剪 | date_range_window_pruning | True | True | 7 | 7 | <none> |
| 主力净流出低于负阈值 | signed_numeric_threshold | True | True | 1 | 1 | <none> |
| 收盘价跌破近3日最低值阈值 | min_window_floor | True | True | 5 | 5 | <none> |
| 日期区间前缀和完整下推 | date_range_prefix_sum_pruning | True | True | 5 | 5 | <none> |
| 等值比较生成Doris标准等号 | sql_equality_operator | True | True | 1 | 1 | <none> |
| 单等号等值比较兼容 | single_equal_operator | True | True | 1 | 1 | <none> |
| 多阶段过滤后再计算均线 | then_filter_window_filter | True | True | 9 | 9 | <none> |
| 按2日均价进行每日排名 | rank_by_window_feature | True | True | 5 | 5 | <none> |
| 指标名大小写容错 | case_insensitive_indicator_name | True | True | 9 | 9 | <none> |
| 市场代码大小写容错 | case_insensitive_market_code | True | True | 10 | 10 | <none> |
| 先全市场排名后过滤A股 | rank_then_market_filter | True | True | 10 | 10 | <none> |
| 连续两次排名重新计算名次 | rank_then_rank_recompute | True | True | 5 | 5 | <none> |
| 行情或资金流条件保留稀疏辅助表 | sparse_auxiliary_left_join | True | True | 13 | 13 | <none> |
| 120日成交量热点窗口直接读取物化列 | hot_window_materialized_prefix | True | True | 0 | 0 | <none> |
| 日期区间资金流前缀和后按低收盘价排名 | date_money_flow_prefix_rank | True | True | 1 | 1 | <none> |
| 日期区间A股换手率每日第一 | date_market_rank_top | True | True | 3 | 3 | <none> |
| 成交量相对三日均量放大 | volume_ratio_to_ma | True | True | 1 | 1 | <none> |
| 过滤A股突破低点后按均换手率排名 | staged_min_filter_rank_by_ma | True | True | 4 | 4 | <none> |
| 日期区间存在资金流出信号 | date_exist_outflow | True | True | 5 | 5 | <none> |
| 日期区间近2日收益率超过5% | date_close_return_rate | True | True | 5 | 5 | <none> |
| 成交量不为零且换手率不低于0.5 | not_equal_and_gte_filter | True | True | 14 | 14 | <none> |
| 日期区间内A股或低价股 | parenthesized_or_with_date_pushdown | True | True | 9 | 9 | <none> |
| 每日低价前50百分比 | rank_ascending_percent_cutoff | True | True | 10 | 10 | <none> |
| 近1日收盘收益率为负 | negative_return_rate_threshold | True | True | 3 | 3 | <none> |
| 跨市场异或低价突破筛选 | market_xor_close_breakout | True | True | 1 | 1 | <none> |

## Negative Diagnostic Cases

| Case | Passed | Expected code | Actual code | Suggestions | Missing suggestion evidence |
|---|---:|---|---|---:|---|
| 未知指标名 | True | UNKNOWN_INDICATOR | UNKNOWN_INDICATOR | 2 | <none> |
| 未知函数 | True | UNKNOWN_FUNCTION | UNKNOWN_FUNCTION | 1 | <none> |
| CONS参数类型错误 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 窗口必须为正数 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 缺少右括号 | True | PARSE_ERROR | PARSE_ERROR | 3 | <none> |
| 字符串未闭合 | True | LEX_ERROR | LEX_ERROR | 3 | <none> |
| rank命名参数错误 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| rank百分比越界 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| rank底部排序方向不一致 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 日期区间起止倒置 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 数字字面量格式错误 | True | LEX_ERROR | LEX_ERROR | 3 | <none> |
| 裸指标列名绕过 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| filter条件不是布尔表达式 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 4 | <none> |
| then阶段不是关系表达式 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 窗口不是整数字面量 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 顶层表达式不是关系或布尔 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 4 | <none> |
| 市场参数不是字符串或标识符 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 除数为零字面量 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 3 | <none> |
| 指标参数不是字符串或标识符 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 日期格式不是ISO | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| filter内裸字段单等号误写 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 除数为零常量表达式 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 3 | <none> |
| 命名参数后跟位置参数 | True | PARSE_ERROR | PARSE_ERROR | 2 | <none> |
| rank顶部排序方向不一致 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| rank顶部数量不是整数 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 3 | <none> |
| rank顶部数量必须为正 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 3 | <none> |
| 重复命名参数 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 日期不存在 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| rank排序方向非法 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 1 | <none> |
| EXIST窗口必须为正 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| 窗口参数不能是字符串 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| rank百分比不能为零 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| date_between参数不足 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| RET不能嵌套窗口表达式 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 3 | <none> |
| rank不能同时使用top和percent | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 3 | <none> |
| RET窗口必须为正 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |
| SUM首参不能是布尔条件 | True | SEMANTIC_ERROR | SEMANTIC_ERROR | 2 | <none> |

## Evidence Policy

- Positive cases must compile, match SQL fragments, match trace fragments, expose expected explain rules, and match the independent SQL/reference result.
- Negative cases must fail safely with the expected diagnostic code and actionable repair suggestions.