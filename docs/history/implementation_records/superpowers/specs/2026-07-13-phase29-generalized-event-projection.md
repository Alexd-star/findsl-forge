# Phase 29 泛化时序事件投影

## 根因

Phase 27 为避免在日期裁剪后再计算 `LAG`，引入了 `PhysicalEventProjection`，但该类型最初只允许 `PhysicalCrossing`。与此同时，直接事件筛选已经能够物化 `PhysicalExtreme`、`PhysicalPosition`、`PhysicalPattern` 和普通指标投影。这种类型不对称使 `position(...,CONS)`、`record_low(...,EXIST)`、均线粘合连续出现等语义在 Logical IR 中成立，却在 Physical IR 阶段被拒绝。

## 设计

`PhysicalEventProjection` 现在承载受控事件定义元组和可选 `PhysicalProjection`。验证器逐类检查：Crossing 必须是同类型数值左右操作数；Extreme 和 Position 必须具有数值输入及合法回看会话数；Pattern 只能是已登记的 `reset/close_together` 布尔谓词；未知事件类型一律拒绝。

后端抽取统一的事件列生成函数。直接筛选与时序投影共同使用以下实现：Crossing 生成当前关系比较与前一会话 `LAG`；Extreme 生成滚动 `MIN/MAX`；Position 生成带零分母保护的五档 CASE；Pattern 生成配置化 `ABS/GREATEST/NULLIF` 表达式。时序层只读取命名事件列和标量投影，不重复解释业务函数。

## 时间序列口径

`近N日` 在时序 `CONS/EXIST` 合同中表示每只证券最近 N 条有效交易观测，而不是市场统一的最近 N 个日期。停牌证券因此会向前取足自身 N 条记录。真实 Doris 对照首次使用市场日期集合时产生少量差异；按既有 `trading_sequence` IR 合同改为逐证券 `ROW_NUMBER ... ORDER BY bizdate DESC` 后，四组完整结果哈希全部一致。该差异及修正保留在证据生成代码中，避免以后混淆“交易所日历窗口”和“证券有效观测序列”。

## 结果

官方漏斗严格迁移从 `729/1097` 增至 `734/1097`，新后端总成功从 752 增至 758。六条新增成功通过递归 Physical IR、事件算子、SQL 安全和占位谓词审计。Position 连续低位、20 会话创新低出现次数、连续贴近 5 日均线、重复回踩 20 日均线四类真实 Doris 场景均非空，独立参考 SQL 与生成 SQL 完整结果哈希一致 `4/4`，结构合同 `4/4`，最高三轮 P95 约 1.37 秒。
