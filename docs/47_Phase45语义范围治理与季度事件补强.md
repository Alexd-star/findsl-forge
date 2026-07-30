# Phase 45 语义范围治理与季度事件补强

## 1. 阶段结论

本阶段继续处理官方 5,799 条工作簿中的严格迁移缺口。上一阶段已经证明，范围问题不能靠字符串相似度批量解决；本阶段因此把“能从已有公共快照证明的语义”与“名称看起来相似但没有唯一依据的语义”分开。前者进入审核配置，后者继续返回稳定诊断。这个边界是故意保留的：对选股系统而言，一个错误的成员集合会把后续排名、聚合和事件结果全部带偏，比暂时拒绝更难发现。

最终严格迁移由 `998/1097` 提升到 `1016/1097`，迁移覆盖率为 `92.62%`；新后端在完整工作簿中成功 `1047` 条。相对 Phase 44 净增 18 条成功，其中 17 条来自版本化范围语义，1 条来自裸“季度”事件周期。严格缺口收敛为 78 条范围成员关系和 3 条非单值 `queryData` 标量关系。

## 2. 本阶段解决的问题

### 2.1 审核范围不再只检查“非空”

原来的组合范围构建器只要求每个来源能够查到成员，并要求交集或并集最终不为空。这个门槛太低：一个解析器表头变化、分页中断或错误快照只要留下 1 条记录，就有可能被当成合法范围。现在，直接映射支持 `minimum_member_count`，组合映射同时支持组件级和结果级最小成员数。构建时先检查每个组件，再检查交集或并集结果；任一条件不满足就失败，不写入运行时目录。

### 2.2 高置信语义映射

本阶段只接入能够说明“原词为什么对应这个集合”的映射。`msic概念` 是 `MSCI概念` 的字母误序，`豆包概率` 是 `豆包概念` 的单字录入错误，属于有明确纠错理由的输入修复。`低价`、`标普概念`、`消费`、`医疗`、`饮料`、`金融`等词则按 A 股范围槽的公共分类解释，并把来源快照、成员数量和解释原因保留在配置与审计报告中。`京东方概念`、`京东方A概念`、`上海电气概念`只有一个官方证券主表命中，因此按唯一证券处理，不扩展成未经证明的产业链概念。

两个组合范围采用稳定证券键求交集。`华为ai眼镜`由华为概念与 AI 眼镜成员求交，`字节跳动算力搭建合作公司`由字节概念与算力概念求交。系统保存分量快照、分量成员数、运算符和最终成员数，Doris 只读取生成后的版本化关系，不把证券名单硬编码进 SQL。

### 2.3 裸“季度”事件周期

`record_low('京', '辽宁指数', '', '季度', '', '', '', '') = True` 的范围在 Phase 44 已经可以解析，但物理规划器把没有数字的“季度”误判为缺少显式交易会话数。根据项目既有周期约定，周、月、季度、年分别按 5、20、60、250 个有效交易观测解释，因此本阶段把裸“季度”“一季度”“一个季度”统一为 60 条交易观测。SQL 仍然由通用 `record_low` 事件窗口生成，使用 `ROWS BETWEEN 59 PRECEDING AND CURRENT ROW`，没有为单个官方问句增加特殊 SQL 分支。

## 3. 数据来源与审计边界

范围成员来自已经落盘的东方财富、百度公开相关板块、公开指数/行业快照和官方证券身份目录。每条配置保留 `source_snapshot_id`，构建器读取快照内容而不是直接接受一份手工证券清单。官方证券身份只用于唯一公司或证券代码解析；不能把公司简称自动扩展为产业链概念。

公共来源的成员是当前截面数据。把当前成员用于历史日期问句可能产生幸存者偏差，因此报告只证明“当前快照下 SQL 可以稳定执行、结果可复核”，不把当前成员集合包装成历史成分。获得历史成分变更数据后，应增加带生效区间的成员快照，再由同一 Physical IR 读取日期有效范围。

本阶段还探测了当前东方财富公开板块目录。`深海经济`、`连扳概念`、`SaaS产品`、`BLacKweLL`、`MATE70`、`光铜共进概念`、`大订单概念`、`混凝土概念`、`国企重组`、`腾讯蓝包概念`、`中心概念板块`和`能源技术服务`均未获得唯一完整的东方财富板块命中，因此没有导入猜测结果。同步脚本同时修复了全未命中时不写报告的问题：现在会生成含 `unresolved` 的审计 JSON，退出码非零，并保证空快照不进入目录。

## 4. Doris 证据

Phase 45 相对于 Phase 44 新增 18 条成功问句，分别在真实 Doris 上执行三轮。18 条的完整结果 SHA-256 均稳定，`18/18 PASS`，11 条返回非空结果，最高三轮 P95 为约 `1.18 s`，低于 10 秒执行目标。范围目录重新装载后，`scope_membership` 为 `207,079` 行，`industry_membership` 为 `40,907` 行，`instrument_rule` 为 `5,686` 行，三张表 Stream Load 过滤行均为 0。

这些证据证明新增计划可以在当前数据截面执行、重复结果稳定且性能达标；它们不能证明所有历史成员关系都正确，也不能证明没有数据域的自定义词语具有某个标准含义。证据中保留空结果，因为空结果是执行事实，不应被改写成非空样例。

## 5. 剩余缺口

剩余 78 条范围缺口对应 71 个真实未解析原子，主要包括 `S板/s板/s版`、`深海经济`、`科技`、数字型自定义板块、口语化策略名、海外或基金范围，以及无法从官方三表恢复的业务集合。它们的共同问题不是 SQL 语法，而是缺少唯一成员关系或缺少适用数据域。3 条 `queryData('', '大盘', ...)` 仍然没有聚合函数，而“大盘”是一个集合，不应从 199 只证券中任选一行作为标量。

下一步若赛题方提供范围字典、历史成分、生效日期或“大盘”默认聚合规则，只需增加新的版本化快照和审核配置；ANTLR、Typed AST、Logical IR、Physical IR 与 Doris SQL 后端不需要为每个词增加分支。

## 6. 复现命令

```powershell
$env:PYTHONPATH = "src"

python scripts/build_curated_scope_alias_snapshot.py `
  --aliases configs/official/external_scope_aliases.json `
  --catalog data/external_catalog/catalog.sqlite3 `
  --runtime configs/official/external_scope_runtime.json `
  --report reports/phase45_curated_scope_alias.json `
  --as-of-date 2026-07-30

python -m findsl.cli official-coverage-funnel `
  --workbook "D:\path\to\选股提槽实例.xlsx" `
  --json-output reports/phase45_scope_governance_funnel.json `
  --report-output reports/phase45_scope_governance_funnel.md

python scripts/extract_external_scope_targets.py `
  --funnel reports/phase45_scope_governance_funnel.json `
  --output reports/phase45_true_remaining_scope_targets.json

pwsh -NoProfile -File scripts/load_external_catalog_doris.ps1

python scripts/audit_funnel_delta_doris.py `
  --previous reports/phase44_composite_scope_funnel.json `
  --current reports/phase45_scope_governance_funnel.json `
  --json-output reports/phase45_scope_governance_delta_doris_audit.json `
  --report-output reports/phase45_scope_governance_delta_doris_audit.md `
  --repeats 3 --timeout-seconds 30 --performance-target-ms 10000
```

## 7. 参考原则

本阶段的目录、验证和物理规划分层，遵循 Apache Calcite 关于 schema/catalog、SQL validation 与关系规划分离的设计思想：[Calcite model](https://calcite.apache.org/docs/model.html)、[Calcite adapters](https://calcite.apache.org/docs/adapter)。跨来源组合只在成员关系层完成，SQL 后端只接收已验证的 Physical IR。对于“深海经济”这类容易受时事和市场口径影响的词，公开报道可以帮助发现候选概念，但不能替代赛题方定义或带生效日期的成分数据；本项目因此保留结构化拒绝。
