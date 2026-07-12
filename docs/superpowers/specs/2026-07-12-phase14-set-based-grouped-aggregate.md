# Phase 14 集合式分组聚合设计

## 1. 为什么不能沿用相关标量子查询

旧后端把 `indicator(...,'SUM','')` 编译为对当前证券逐行执行的相关子查询。该写法容易理解，但在千万级行情表上会重复扫描相同日期窗口，Doris 难以充分发挥分布式聚合能力，也不利于后续代价模型选择前缀表或物化视图。

本阶段采用集合式关系计划：先一次扫描受约束日期和市场，按证券稳定键聚合；再筛选满足阈值的证券资格集；最后与基础行情最新快照连接。计划中不存在每只证券相关执行的 aggregate subquery。

## 2. PhysicalGroupedAggregate

节点包含：

- 输入关系：单一指标资源及其稳定锚点；
- measure：直接列或受控派生表达式；
- function：`sum/avg/max/min`；
- comparator 与数值 bound；
- anchor resource：用于恢复标准输出键和最新交易日。

输入资源必须能通过 catalog 找到具有 `mktcode,tgtcode,bizdate` 的稳定锚点。聚合函数和比较符均为闭集，bound 必须通过 typed literal 进入物理层。

## 3. Doris 关系形态

生成 SQL 的逻辑结构如下：

```text
constrained source rows
  -> GROUP BY mktcode,tgtcode + aggregate metric
  -> filter metric into qualified security keys
  -> INNER JOIN latest official_basic snapshot
  -> mktcode,tgtcode,bizdate
```

日期为 `近5日` 时，源关系先应用最近五个不同交易日的集合成员谓词。资金流等扩展指标仍由 `official_basic` 锚定后 LEFT JOIN 扩展表，分组键取锚点证券键，避免丢失基础证券全集或跨日连接。

## 4. 当前边界

- 支持一个直接聚合调用与一个数值 literal 比较。
- 支持 `SUM/AVG/MAX/MIN`。
- 多个聚合 measure 需要命名 measure 和 alias propagation，当前返回 `PHYSICAL_AGGREGATE_COMPOSITION_UNSUPPORTED`。
- `GROWTH` 系列需要首末值或窗口状态合同，返回 `PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED`。
- rank over aggregate 需要在 aggregate 输出上建立 rank window，仍由 rank 阶段实现。
- 带 `filter_scope` 的聚合仍因官方缺少行业/概念成员关系表而不生成 SQL。

## 5. 证据

`scripts/collect_phase14_aggregate_evidence.py` 使用最近五个真实交易日，分别构造 `SUM/AVG/MAX/MIN` 的独立 `GROUP BY/HAVING` reference SQL。四组生成结果均与 reference 完整行集 SHA-256 一致，并通过集合式形态检查。

迁移漏斗由 `218/1097` 提升到 `231/1097`。这 13 条是已具备单聚合、单资源、明确比较合同的语料；59 条聚合组合和 22 条增长类聚合继续保留独立错误码，便于后续按价值推进。
