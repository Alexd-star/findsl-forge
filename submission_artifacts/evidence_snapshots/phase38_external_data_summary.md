# Phase 38 公开外部数据与 Doris 证据摘要

## 版本与口径

- 代码 Git HEAD：`1021dd93fe1d89e0519d31f91e20cb318bbc740b`
- 官方工作簿问句：`5799`
- 旧严格成功集：`1097`
- 新架构后端成功：`976`
- 旧严格成功集已迁移：`947/1097`，即 `86.33%`
- 剩余严格缺口：`150`，其中 `148` 条缺范围成员关系，`2` 条已有指数成员但缺指数自身行情标量

以上数字来自 `phase38_public_index_funnel.json`。成功表示问句经过 ANTLR4 前端、Typed AST、Logical IR、优化器、Physical IR、SQLGlot Doris AST 和后端安全校验；它不自动等同于真实 Doris 行集正确，因此新增项另做执行审计。

## 外部目录

| 表 | 期望行数 | Doris 实际行数 | Stream Load | 过滤行 |
|---|---:|---:|---|---:|
| `findsl_ext.scope_membership` | 61862 | 61862 | Success | 0 |
| `findsl_ext.industry_membership` | 28386 | 28386 | Success | 0 |
| `findsl_ext.instrument_rule` | 5686 | 5686 | Success | 0 |
| `findsl_ext.index_quote` | 14533 | 14533 | Success | 0 |

外部目录装载见 `external_catalog_doris_load.json`；指数行情见 `index_quote_sync.json` 和 `index_quote_doris_load.json`。这些表位于独立数据库，SQL 同时固定来源快照和范围代码，不与赛题方提供的 `newzl` 三张事实表混称“官方数据”。

## 本轮新增验证

Sina 全量板块同步发现 290 个板块，成功 290 个，失败 0 个，生成 21297 条范围成员关系和 5160 条行业关系，见 `sina_sector_sync.json`。由此新增的 3 条后端成功均在真实 Doris 上通过，见 `phase37_sina_delta_doris_audit.json`。

AKShare 公共指数 provider 补入上证周期、380 稳定、上证上游、上证指数、科创 50 等明确指数。Phase 38 相对 Phase 37 新增的 9 条 SQL 均重复执行 3 次，`9/9 PASS`，结果行数和 SHA-256 稳定，最高 P95 约 1.61 秒，见 `phase38_public_index_delta_doris_audit.json`。

## 语义纠偏

本轮禁止仅凭删除后缀把普通范围映射为指数。系统主动撤回 7 条此前可执行但含义不可靠的映射，例如“金融公司”不再自动等同于“金融指数”。因此 Phase 38 的净迁移增量小于新增执行成功数。该处理降低表面覆盖率，却消除了可被评委直接质疑的集合偷换。

真实执行还发现 prefix CTE 未透传 `lastPx` 的 renderer 缺陷。修复后，动态 24 日均线穿越事件使用 `prefix_values.lastPx`，外层范围和日期条件使用 `event_rows`，对应上证周期问句已纳入 `9/9` 通过审计。

## 证据限制

1. 第三方板块成员只代表记录的快照日期，不代表赛题方内部自定义板块。
2. 空结果执行成功只能证明 SQL 合法、计划可运行和性能达标，不能单独证明金融语义正确。
3. 同花顺概念分页本轮持续触发限流，没有任何不完整概念被导入。
4. `S板`、自定义题材、错别字和没有标准成员表的自由文本仍明确拒绝，不用常量真假或猜测集合补齐。
5. 1.61 秒是当前本地 Doris 与本轮数据规模下的证据值，不外推为生产 SLA；赛题硬指标仍以低于 10 秒判定。
