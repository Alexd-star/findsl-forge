# Phase 10 同实体多资源稳定键连接设计

## 1. 问题边界

官方问句经常把基础行情、资金流、证券静态信息和技术指标写在同一表达式中。Phase 9 以前，物理规划器要求所有字段来自同一资源，因此即使每个字段都有真实 Doris 映射，组合问句仍会以 `PHYSICAL_MULTI_RESOURCE_UNSUPPORTED` 终止。

本阶段解决的是“同一证券实体、可由 catalog 稳定键精确连接”的普通关系查询。它不顺带处理跨资源时序、跨资源聚合、不同业务实体连接，也不把缺失的概念板块关系猜成证券名称或行业字段。

## 2. 关系模型

四类已落地资源共享 `logical_entity=market_observation`：

| 资源 | 作用 | 稳定键 |
|---|---|---|
| `official_basic` | 基础行情和结果证券全集 | `mktcode,tgtcode,bizdate` |
| `official_ext` | 资金流和扩展行情 | `mktcode,tgtcode,bizdate` |
| `official_security` | 证券名称、市场板块和静态标识 | `mktcode,tgtcode` |
| `official_technical` | 均线等技术指标 | `mktcode,tgtcode,bizdate` |

规划器固定以 `official_basic` 作为稳定锚点。右侧资源按资源 ID 稳定排序，构造左深 Join 树。每一条连接边只采用锚点与右表 `stable_keys` 的有序交集，并要求至少包含 `mktcode` 和 `tgtcode`。因此静态证券维表不会被错误要求提供 `bizdate`，有日期的事实表也不会遗漏日期键而形成跨日笛卡尔放大。

## 3. Physical IR

`PhysicalTableScan` 表示不隐式附带锚点的原始物理资源扫描；`PhysicalJoin` 表示显式关系连接，包含左右输入、连接类型和成对的 typed `PhysicalColumn` 键。单资源路径继续使用原有 `PhysicalScan`，避免改变已经验证的 SQL 形态。

多资源表达式只允许引用 Join 树中实际存在的资源。验证器同时检查：

1. 左右资源属于同一逻辑实体；
2. 两侧键名一致；
3. 键在各自 catalog 中声明为稳定键；
4. 连接类型只能是 `inner` 或 `left`；
5. 表扫描列不得冒充其他资源的列。

## 4. SQLGlot 后端

后端把左深 Join 树展开为一个星型 Doris `SELECT`。资源 ID 同时作为受控表别名，列渲染前会核验别名是否存在于当前关系树。输出键始终来自锚点资源，右表使用 `LEFT JOIN` 保存基础行情证券全集；当筛选谓词要求右表字段非空时，关系语义自然收敛为匹配行，与独立 `INNER JOIN` reference SQL 的结果一致。

多个函数携带相同市场或日期条件时，物理谓词归一器只对 `AND` 合取项进行规范节点 ID 去重，不跨 `OR` 改写，也不合并非等价范围。三个“今日”函数因此只保留一个最新交易日子查询。

## 5. 明确拒绝项

- 多资源 `CONS/EXIST` 返回 `PHYSICAL_TEMPORAL_MULTI_RESOURCE_UNSUPPORTED`。时序谓词需要先定义对齐日历、空值和缺行合同，不能套用普通 Join。
- 不同 `logical_entity` 的资源拒绝连接。
- 无共同证券稳定键或无法推导唯一锚点时拒绝规划。
- `filter_scope` 中的概念、行业和自定义板块在没有官方成员关系表时仍不生成 SQL。
- 聚合、相关子查询和 chained rank 继续由各自物理节点负责，不在 Join 阶段近似。

## 6. 验证证据

自动测试覆盖两资源、三资源、静态维表双键、日期事实表三键、SQLGlot 安全渲染和重复最新日约束去重。`scripts/collect_phase10_join_evidence.py` 另外在真实 Doris 上执行五组问句，并与人工书写的 reference SQL 比较完整结果行集 SHA-256。

当前官方迁移漏斗为 `135/1097（12.31%）`，比 Phase 9 的 `107/1097` 增加 28 条。这个数字表示旧严格成功集进入新后端的迁移覆盖，不是 5,799 条语料的正确率。版本化证据位于 `submission_artifacts/evidence_snapshots/phase10_join_doris.*` 与 `phase10_join_funnel.*`。
