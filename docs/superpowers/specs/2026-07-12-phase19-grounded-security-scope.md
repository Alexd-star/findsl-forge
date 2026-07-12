# Phase 19 可验证证券名称范围与命名标量关系

## 1. 数据事实与设计边界

Phase 18 后，旧严格成功集有 259 条问句停在 `PHYSICAL_CONSTRAINT_UNSUPPORTED`。逐条审计发现这些约束全部来自 `filter_scope` 或 `queryData` 的关键词槽。真实 Doris 代码表共有 5,686 行，但 `hyBlkRefName` 为空，官方资料没有提供概念、行业、指数或自定义板块的证券成员关系。因此“鸿蒙概念”“白酒行业”“沪深300医药”等范围不能被改写成全市场，也不能用空结果冒充支持。

同一批问句中存在可由证券主数据精确证明的范围，例如华泰证券、贵州茅台、中科曙光和“珀莱雅(603605)”。本阶段只开放这类可验证范围，并把其余范围转成稳定的数据不可用诊断。

## 2. 类型与物理计划

Domain IR 新增范围原子、补集、交集和并集，优先级与市场集合保持一致。物理层加载版本化证券目录，只接受目录中存在的精确名称；带六位代码的形式还必须同时匹配名称、市场号和证券代码。

范围筛选会把 `official_security` 加入资源集合，按照 catalog 声明的 `(mktcode,tgtcode)` 与行情锚点连接。范围谓词引用真实 `official_security.name`，不复用空的 `hyBlkRefName`，也不向行情表注入不存在的名称列。

`queryData` 需要区别候选证券值与外部 benchmark 值。直接值通过 `PhysicalNamedScalar` 形成单行关系；全局聚合通过 `group_by_security=False` 的 `PhysicalAggregateGroup` 形成单值关系。二者都以 Cross Join 进入外层谓词，因此 benchmark 的证券名称约束不会泄漏到候选全集。多证券或范围日期无法保证单值时继续拒绝。

## 3. 主数据可回溯性

`scripts/generate_official_security_scope_catalog.py` 从 Doris 证券代码表按 `(mktcode,tgtcode)` 稳定排序，输出名称、市场号和代码，并对规范 TSV 内容计算 SHA-256。当前目录包含 5,686 条证券，源哈希为 `606330117bced197063c7f9bb2531f8a135150c5c982d7289c62265f68f2a635`。`--check` 会重新读取实时 Doris 并拒绝任何漂移。

## 4. 结果与证据

官方迁移覆盖由 `393/1097` 提升到 `406/1097（37.01%）`，新后端总成功数达到 413。原 259 条笼统约束错误被拆成 13 条真实迁移和 244 条 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`。后者不是开发遗漏，而是当前官方数据包缺少成员关系的明确边界。

真实 Doris 证据覆盖证券全集、市场与名称叠加、名称代码双校验、直接 benchmark、全局聚合 benchmark、名称范围排名和名称并集。七组结果均非空，生成 SQL 与独立 reference SQL 的完整 `(mktcode,tgtcode,bizdate)` 行集 SHA-256 一致，结果为 `7/7 PASS`；目录源哈希与实时 Doris 也一致。

## 5. 后续方向

下一阶段不再把 244 条缺失成员数据作为可编码缺口。高收益工作应转向 95 条物理映射、80 条表达式、50 条聚合函数和 37 条近似比较策略，同时继续修复已暴露的单条关系后端错误。若赛题方后续提供概念或行业成员表，可复用本阶段 Scope Set IR，只需增加新的成员关系 catalog 与物理资源，不需要改写语法和逻辑层。
