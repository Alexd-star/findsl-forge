# 官方语料数据域与能力需求审计

- Git HEAD：`a323d96ca63728b4ac9dbba3d5599c56a6cd135d`
- 数据配置：`competition-v1`
- 语料行数：`5799`

## 能力分类

| 分类 | 条数 |
|---|---:|
| `CAPABILITY_GAP` | 243 |
| `DATA_UNAVAILABLE` | 1998 |
| `INVALID_INPUT` | 2399 |
| `SUPPORTED` | 1159 |

## 数据域需求

| 能力分类 | 数据域 | 当前状态 | 涉及问句 |
|---|---|---|---:|
| `CAPABILITY_GAP` | `daily_market_quote` | `available` | 186 |
| `CAPABILITY_GAP` | `extended_daily_quote` | `available` | 46 |
| `CAPABILITY_GAP` | `group_analytics` | `unsupported` | 136 |
| `CAPABILITY_GAP` | `index_market_data` | `available` | 14 |
| `CAPABILITY_GAP` | `security_identity` | `available` | 14 |
| `CAPABILITY_GAP` | `technical_indicator` | `derived` | 30 |
| `CAPABILITY_GAP` | `unclassified_indicator` | `unsupported` | 3 |
| `DATA_UNAVAILABLE` | `advanced_pattern` | `unsupported` | 81 |
| `DATA_UNAVAILABLE` | `cross_market_quote` | `not_loaded` | 96 |
| `DATA_UNAVAILABLE` | `currency_market_data` | `not_loaded` | 6 |
| `DATA_UNAVAILABLE` | `daily_market_quote` | `available` | 1640 |
| `DATA_UNAVAILABLE` | `derivative_market_data` | `not_loaded` | 12 |
| `DATA_UNAVAILABLE` | `extended_daily_quote` | `available` | 161 |
| `DATA_UNAVAILABLE` | `financial_statement` | `not_loaded` | 700 |
| `DATA_UNAVAILABLE` | `fixed_income_market_data` | `not_loaded` | 49 |
| `DATA_UNAVAILABLE` | `fund_market_data` | `not_loaded` | 257 |
| `DATA_UNAVAILABLE` | `fund_reference` | `not_loaded` | 81 |
| `DATA_UNAVAILABLE` | `group_analytics` | `unsupported` | 94 |
| `DATA_UNAVAILABLE` | `index_market_data` | `available` | 9 |
| `DATA_UNAVAILABLE` | `index_reference` | `available` | 1 |
| `DATA_UNAVAILABLE` | `intraday_quote` | `not_loaded` | 70 |
| `DATA_UNAVAILABLE` | `private_account` | `private_required` | 117 |
| `DATA_UNAVAILABLE` | `scope_membership` | `available` | 78 |
| `DATA_UNAVAILABLE` | `security_identity` | `available` | 152 |
| `DATA_UNAVAILABLE` | `technical_indicator` | `derived` | 134 |
| `DATA_UNAVAILABLE` | `unclassified_indicator` | `unsupported` | 805 |
| `INVALID_INPUT` | `daily_market_quote` | `available` | 29 |
| `INVALID_INPUT` | `extended_daily_quote` | `available` | 5 |
| `INVALID_INPUT` | `group_analytics` | `unsupported` | 1 |
| `INVALID_INPUT` | `security_identity` | `available` | 2 |
| `INVALID_INPUT` | `technical_indicator` | `derived` | 10 |
| `INVALID_INPUT` | `unclassified_indicator` | `unsupported` | 2 |

> 同一问句可能同时需要多个数据域，因此本表不能横向求和。 `not_loaded` 表示已有明确契约但当前没有合规快照； `unsupported` 表示还缺业务定义或编译能力，不能靠下载数据解决。

## 无数据域依赖的剩余能力

- `INVALID_INPUT`：2370 条。
