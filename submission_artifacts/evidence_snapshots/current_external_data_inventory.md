# 外部补充数据清单与来源审计

- 已验证源码 HEAD：`a1158305022e708163fb6cd06377a0bad00fd5c7`
- 数据目录 SHA-256：`8b7c857265647ca19b07521a52b09149f3af4c64ed5ee1b5bd36de152005a7c7`
- 快照：`24` 个
- 已登记来源：`11` 个
- 范围成员：`220295` 行
- 行业成员：`40907` 行
- 交易规则：`5686` 行

## 运行模式

| 模式 | 使用外部数据 | 离线可复现 | 说明 |
|---|---|---|---|
| `enriched_public` | True | False | 编译配置已固化且请求期不访问网络；执行外部范围 SQL 前仍须按来源许可同步并装载对应快照。 |
| `official_only` | False | True | 仅使用赛题方数据包；缺失的行业、概念、指数行情和交易规则返回确定性拒绝。 |

## 快照明细

| 来源 | 日期 | 范围成员 | 行业成员 | 交易规则 | 时间模型 | 权威等级 | 再分发处理 |
|---|---|---:|---:|---:|---|---|---|
| `akshare-eastmoney-index` | 2026-07-13 | 1612 | 0 | 0 | `current_snapshot` | `open_source_adapter` | `academic_only` |
| `akshare-public-index` | 2026-07-13 | 3867 | 0 | 0 | `current_snapshot` | `open_source_adapter` | `academic_only` |
| `akshare-security-identity` | 2026-07-13 | 5529 | 0 | 0 | `dated_snapshot` | `open_source_adapter` | `academic_only` |
| `baidu-related-block` | 2026-07-15 | 117908 | 11057 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `baostock` | 2026-07-13 | 0 | 5203 | 0 | `dated_snapshot` | `public_data_service` | `review_required` |
| `cnindex` | 2026-07-13 | 1196 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `cnindex` | 2026-07-13 | 60 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `cnindex` | 2026-07-13 | 697 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `cnindex` | 2026-07-13 | 1256 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `csindex` | 2026-07-13 | 20 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `csindex` | 2026-07-13 | 21 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `csindex` | 2026-07-30 | 300 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `csindex` | 2026-07-30 | 189 | 0 | 0 | `effective_dated` | `official_publisher` | `review_required` |
| `curated-scope-alias` | 2026-07-13 | 1681 | 0 | 0 | `project_policy` | `project_curated` | `derived_snapshot_only` |
| `curated-scope-alias` | 2026-07-15 | 6285 | 0 | 0 | `project_policy` | `project_curated` | `derived_snapshot_only` |
| `curated-scope-alias` | 2026-07-30 | 10832 | 0 | 0 | `project_policy` | `project_curated` | `derived_snapshot_only` |
| `curated-scope-alias` | 2026-08-01 | 13027 | 0 | 0 | `project_policy` | `project_curated` | `derived_snapshot_only` |
| `eastmoney` | 2026-07-13 | 16365 | 16365 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `eastmoney` | 2026-07-13 | 8261 | 1658 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `eastmoney` | 2026-07-15 | 7113 | 1341 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `eastmoney` | 2026-07-30 | 106 | 0 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `eastmoney` | 2026-07-30 | 2673 | 123 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `sina-finance` | 2026-07-13 | 21297 | 5160 | 0 | `current_snapshot` | `public_information_platform` | `derived_snapshot_only` |
| `sse-szse-bse` | 2026-07-13 | 0 | 0 | 5686 | `effective_dated` | `official_publisher` | `review_required` |

> `official_only` 不引用这些外部表，可以随官方数据包离线复现。`enriched_public` 的编译请求不会临时访问网络，但干净环境执行前必须按许可同步并装载对应快照；当前成员不得倒推为采集日前的历史成员。
