# Phase 20：受控指标映射与窗口事件关系

## 1. 阶段目标

Phase 20 合并处理 Phase 19 漏斗中的两类高价值缺口：95 条 `PHYSICAL_PLAN_UNAVAILABLE` 和 81 条 `PHYSICAL_EXPRESSION_UNSUPPORTED`。目标不是把旧后端字符串 SQL 原样搬入新后端，而是确认每个指标的真实字段、单位、资源和空值语义，再用 Physical IR 与 SQLGlot AST 表达。凡官方三表及确定性派生表无法证明的能力，继续返回结构化数据缺失诊断。

## 2. 数据事实与边界

本阶段以实时 Doris `information_schema.columns` 和 13,650,347 行行情骨架为准。`hsj_stock_hq_basic` 提供价格、成交、委托、市值基础字段；`hsj_stock_hq_ext` 提供竞价、资金流和行情扩展字段；`hsj_stock_hq_basic_technical` 由官方 OHLCV 确定性构建，提供均线、均量、K 线形态和趋势标志。比例类整数按官方万分位存储除以 10,000，价格类整数同样按 10,000 缩放，成交均价采用 `turnover / volume / 100`。实库抽样显示该公式与最新价数量级一致。

`是否T+0` 没有来源字段；`涨停未封板` 必须同时使用扩展表的开板事件和基础表的最终涨停状态，不能用单一字段冒充。行业、概念、指数和自定义板块成员关系仍缺失，其中 `hyBlkRefName` 在 5,686 行证券主数据中全部为空。因此这些能力不进入成功覆盖。

## 3. 受控映射

`configs/official/physical_expressions.json` 新增 29 个定义。直接公式包括流通市值、振幅、成交均价、委比、委差、每股净资产、静态市盈率、涨跌停价、支撑位和上影线；扩展行情包括 3 分钟涨速、集合竞价涨幅、主力及散户占比、最大回撤和涨停炸板；技术表包括阳线、阴线、十字星、放量和均线多空排列。表达式注册表只允许列、字面量、四则运算、安全除法、比较、布尔组合、取负和 `COALESCE`，不存在原始 SQL 逃生口。

## 4. 窗口事件物理计划

`PhysicalEventFilter` 把窗口计算与最终过滤分成两层。内层关系按 `(mktcode,tgtcode)` 分区、按 `bizdate` 排序，生成事件列和普通指标投影；外层才处理 `event=True`、市场、日期和其他标量条件。这样 `LAG`、滚动 `MIN/MAX` 不会出现在 `WHERE`，符合 Doris 分析函数执行阶段。

`cross_above`、`cross_down` 和 `golden_cross` 同时比较当前左右值以及上一交易会话左右值。`record_high/record_low` 使用包含当前行的交易会话窗口。日、周、月、季度和年分别转换为 1、5、20、60 和 250 个交易会话；“历史”使用 `UNBOUNDED PRECEDING`。`position` 在同一窗口中计算最小值和最大值，依次判断“最低、最高、低、高、中”，低区和高区阈值为 0.25 与 0.75。

`reset` 与 `close_together` 的阈值来自 `configs/official_technical_patterns.json`。前者要求左右指标相对距离不超过 2%，且左值不能低于右值的 99.5%；后者要求相对距离不超过两者绝对值较大者的 3%。分母统一用 `NULLIF(...,0)`，不把零分母改造成真值。

## 5. 根因修复

真实 Doris 首轮审计发现 `涨停炸板=True AND 今日` 返回 11,104 行，而参考结果为 70 行。根因是 `PhysicalComparison` 的左侧为 `OR` 时没有强制括号，SQL 被解释为 `a OR (b=True AND date)`。后端现对比较运算两侧的复合 `PhysicalBinary` 统一加 `Paren`，修复后完整结果集 SHA-256 一致。相关回归测试覆盖复合布尔指标和日期条件，防止同类优先级泄漏。

## 6. 验证结果

官方漏斗由 `406/1097（37.01%）` 提升至 `534/1097（48.68%）`，新后端总成功数由 413 增至 548。原 95 条物理计划缺口只剩 3 条，分别是两个 T+0 问句和一个需要跨资源专门合同的涨停未封板问句。原 81 条通用表达式缺口降为 0；15 条 `belong_industry` 问句改记 `PHYSICAL_INDUSTRY_DATA_UNAVAILABLE`，不再与代码能力混淆。

`scripts/collect_phase20_mapping_event_evidence.py` 在真实 Doris 上覆盖 13 类非空用例，包括基本表公式、扩展表比例、技术布尔组合、炸板事件、同资源与跨资源交叉、60 会话新高、历史新低、事件与标量组合、两类技术形态和 10 会话位置。五轮生成 SQL 均与独立参考 SQL 完整结果集哈希一致 `13/13`。版本化证据位于 `submission_artifacts/evidence_snapshots/phase20_mapping_event_doris.*` 和 `phase20_capability_funnel.*`。

## 7. 后续优先级

下一能力包应优先处理聚合函数与近似比较策略：52 条聚合函数缺口、43 条近似比较策略和 20 条排名表达式具有明确代码价值。254 条证券范围缺口、106 条领域能力缺口、22 条数据域缺口及 15 条行业关系缺口主要受官方数据限制，不应通过假 SQL 提升覆盖率。窗口事件的多日期关系和 `CONS/EXIST` 组合仍需专门的集合计划，不能把多个日期条件压到同一行。
