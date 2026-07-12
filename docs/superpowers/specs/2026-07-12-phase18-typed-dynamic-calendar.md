# Phase 18 类型化动态日期与交易日边界设计

## 1. 问题与边界

Phase 17 后，旧严格成功集仍有 82 条问句停在 `PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED`。主要表达包括当前或上一自然周期、滚动周/月/年、缺少年份的月日、相对交易日切片，以及某个自然周期或固定日期前后的 N 个交易日。旧实现能够用固定 Python 日期生成部分 SQL，但该做法会把编译时钟、数据最新日期和交易所会话混为一体，不能作为生产编译器语义。

本阶段统一以 Doris 基础行情表的 `MAX(bizdate)` 作为动态锚点。自然周、月、季度和年使用自然日历边界；带“日、天、交易日”的窗口使用基础行情表去重后的交易日序列。缺失数据域仍返回确定性错误，不以日期扩展掩盖其他能力缺口。

## 2. 类型合同

Domain IR 的 `DateConstraint` 增加 `offset/month/day`，并形成以下合同：

- `dynamic_period`：当前或历史完整自然周期，包含 `unit` 与非正 `offset`。
- `recent_calendar`：以最新数据日为终点的滚动周、月、年窗口。
- `anchor_calendar`：以最新数据年份或月份补全的月、月日或日。
- `session_slice`：最近交易日序列中的 `[offset, offset+amount)` 切片。
- `before_period_sessions`：某个自然周期起点之前的 N 个真实交易日。
- `after_date_sessions`：某个明确日期之后的 N 个真实交易日。

Physical IR 使用 `PhysicalDynamicDateRange`、`PhysicalRecentSessions` 和 `PhysicalSessionBoundaryRange` 表达以上合同。验证器要求日期列必须是 catalog 声明的分区列，数量必须为正，动态 offset 不得指向未来，周期单位和范围种类必须匹配。

## 3. SQLGlot 物理化

动态自然周期通过 SQLGlot AST 组合 `MAX`、`DATE_TRUNC`、`DATE_ADD` 与 `DATE_SUB`，不注入原始 SQL 片段。当前周期的结束日为最新数据日；上一周期的结束日为当前周期起点前一日。滚动 N 周覆盖 `N*7` 个自然日，滚动 N 月采用 `DATE_SUB(anchor,N MONTH)+1 DAY`，滚动 N 年从 `anchor.year-N+1` 的 1 月 1 日开始。

交易日集合使用 `SELECT bizdate ... GROUP BY bizdate ORDER BY bizdate LIMIT/OFFSET`。周期前置集合增加 `< period_start`，固定日期后置集合增加 `> explicit_date`。这类计划能够跨周末、法定节假日和停市日保持正确，不使用 `DATE_SUB(...,N DAY)` 近似。

## 4. 验证结果

官方 5,799 条语料的迁移覆盖由 `317/1097` 提升到 `393/1097`，新后端总成功数达到 400；旧严格成功集中的日期物理化缺口由 82 条降为 0。其余失败会继续落入约束、数据域、表达式、聚合或计划错误码，没有被日期支持误计为成功。

`scripts/collect_phase18_dynamic_date_evidence.py` 从 Doris 的 4,631 个不同交易日独立解析九组显式日期集合。当前月、上周、去年、近两个月、本季度、锚定月日、周前交易日、固定日期后交易日及前置交易日切片均与生成 SQL 的完整 `(mktcode,tgtcode,bizdate)` 行集 SHA-256 一致，结果为 `9/9 PASS`。当前证据快照的最高五次 P95 约 0.59 秒。

## 5. 后续工作

动态日期缺口已经清零，但日期能力释放出的组合问句会进入下一层真实缺口。例如范围标量与聚合的混合需要明确集合语义，时序结果后接排名需要让排名后端识别关系输入。下一阶段应优先处理 `PHYSICAL_CONSTRAINT_UNSUPPORTED` 的可落地子类，同时修复由动态日期暴露出的单条 `DORIS_RELATION_UNAVAILABLE`，保持“先有类型合同，再有物理计划，最后做真实 Doris 对拍”的推进方式。
