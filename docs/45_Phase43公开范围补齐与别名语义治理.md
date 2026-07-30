# Phase 43 公开范围补齐与别名语义治理

## 1. 阶段结论

Phase 43 继续处理 Phase 41 遗留的范围成员缺口，但没有把字符串相似度当成正确性。系统先从官方 5,799 条工作簿中提取旧严格后端成功而新架构失败的问句，再用当前官方证券目录和外部运行时目录逐个反查范围原子。复核发现，旧提取脚本会把失败问句中已经解析成功的其他范围一并列入待补清单，因而把“问句涉及的范围”误写成“真正缺失的范围”。本轮修正统计口径后，报告同时保存全部范围数、已解析范围数和真实未解析范围数。

最终新架构迁移 `990/1097`，覆盖率为 `90.25%`，新后端在完整工作簿中成功 `1021` 条。相对 Phase 41 的 `971/1097` 和 1,000 条后端成功，本阶段净增 19 条严格迁移、21 条后端成功。剩余 107 条严格缺口中，104 条缺少可唯一证明的范围成员关系，3 条是多证券“大盘”范围在未指定聚合函数时无法形成单一 `queryData` 标量。系统继续拒绝这三条，而不是从 199 只大盘股中任意取一行。

## 2. 数据来源与完整性门禁

本阶段使用三个已经版本化的来源层次。第一层是东方财富公开板块目录，先完整发现 1,000 个行业和概念板块，再只下载目标板块的全部成分页；来源声明总数未取满、分页提前结束或任一目标失败时，整批快照不导入。第二层是 Phase 41 已完成的百度全市场证券侧分类快照，它覆盖 `5529/5529` 只版本化 A 股证券。第三层是 5,686 只证券身份快照，用于公司简称与证券稳定键的精确对应。

本轮两批东方财富快照分别补入字节跳动、熔盐储能等目标，以及 AIGC、白酒、白酒行业、胎压监测、低空经济、教育、华为概念、AI 应用、机器人、银行、贵金属、新能源、工业母机、IPv6、固态电池、水力发电和 MSCI 中国。人工审核别名只引用已经存在的完整快照，不自行编造成员。`SHEIN` 按 A 股范围槽解释为公开“希音合作商”概念；`大盘` 限定为“大盘股”，不偷换成某个宽基指数；`公共服务` 在行业槽中按“公用事业”解释；这些政策均把原词、目标范围、来源快照和理由写入配置，赛题方口径不同时可以单独撤回。

同花顺公开成分页在本机只能稳定取得前几页，随后会转到登录页。此前命令只有显式传入 `--require-complete` 才拒绝部分数据，自动化调用一旦漏写参数便可能导入残缺快照。现在完整性是默认策略，只有人工明确使用 `--allow-partial` 才允许部分导入；默认拒绝会写出失败报告并返回非零退出码。由于已有完整来源覆盖本轮目标，未完成的同花顺缓存没有进入目录，相关临时配置也没有作为交付能力保留。

## 3. 别名冲突修复

范围匹配会去除“概念、行业、板块”等后缀，用于识别 `工业母机概念 -> 工业母机` 这类唯一对应关系。这个规则曾暴露一个更隐蔽的问题：`白酒行业` 和 `白酒` 规范化后都是“白酒”，人工别名 `白酒行业 -> 白酒Ⅱ` 因而也会改写来源中原本精确存在的“白酒”概念。

修复后的优先级是：来源名称逐字精确命中、显式审核别名、带类型提示的规范化匹配、满足阈值和唯一差值的模糊匹配。也就是说，公开目录中存在精确名称时不允许别名抢占；只有精确名称不存在时，审核别名才参与选择。自动测试固定了 `白酒 -> BK0896` 与 `白酒行业 -> BK1277` 的分离结果，防止后续重构再次合并两种语义。

这一处理与 Apache Calcite 的规划思想一致：解析、验证、逻辑关系和物理实现应分层，等价变换必须先保证语义正确，再比较成本。Calcite 官方资料将关系代数树、规则变换和成本选择分开说明，项目也据此把范围解析保留在目录和 Physical IR 层，而不是在 SQL 字符串中临时替换。参考资料：[Apache Calcite Algebra](https://calcite.apache.org/docs/algebra.html)、[Apache Calcite Adapters and Planner Rules](https://calcite.apache.org/docs/adapter)。

## 4. Doris 装载与真实执行

最终目录装入 Doris 后，`findsl_ext.scope_membership` 为 203,181 行，`industry_membership` 为 40,907 行，`instrument_rule` 为 5,686 行。装载脚本逐表清空后执行严格 Stream Load，要求清单行数与 Doris 实际行数完全相等，并把最大过滤比例设为 0；三张表均返回 `Success`，过滤行均为 0。

Phase 43 相对 Phase 41 新增的 21 条后端成功问句全部进入差量审计。每条 SQL 在真实 Doris 上执行三次；无确定顺序的集合查询按全部投影列建立规范顺序，已有 `ORDER BY/LIMIT` 合同的查询保持生成顺序。21 条问句均得到稳定的完整结果 SHA-256，11 条返回非空结果，最高三轮 P95 为 `2389.109 ms`，低于赛题 10 秒阈值。最大结果集为 4,546 行，说明审计没有只挑选单行或空结果样例。

本报告证明这些 SQL 在当前快照上可执行、重复结果稳定且性能达标。空结果仍不能单独证明业务语义，因此别名证据还必须包含非空来源成员、来源快照摘要和明确映射理由。外部成员是 2026 年截面，解释历史日期问句时存在成员幸存者偏差；在没有历史成分变更数据前，报告必须保留这项边界。

## 5. 剩余缺口与停止条件

剩余 104 条范围缺口对应 97 个真实未解析原子。高频项包括 `S板/s板/s版`、`深海经济`、`科技`、`宁夏算力概念`、`英美贸易业`、`金融公司`、数字型自定义板块和若干口语化策略名称。它们不是简单的拼写问题：例如“科技”可能指行业、主题、风格指数或用户自定义组合；“S板”可能指历史特殊标记、区域市场或私有板块；数字 `100429/994338` 没有公开代码体系可供唯一反查。把这些词映射到相似名称会提高表面覆盖率，却会降低评委复核时的可信度。

三条 `PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE` 也应保留。`queryData('', '大盘', '涨幅', '今天', '')` 没有给出 `AVG/SUM/MAX/MIN`，而“大盘”当前解析为 199 只证券的集合；关系结果不是单值，无法安全地与一个证券指标比较。只有赛题方确认默认聚合规则，或将“大盘”定义为具有自身行情的唯一指数后，才能把它们变成标量计划。

因此，Phase 43 的完成标准不是把数字强行改成 1097，而是把所有公开可证明项接入、把不完整来源默认拒绝、把新增 SQL 全部放到真实 Doris 审计，并让剩余失败都带稳定原因。后续若获得赛题方范围表或语义确认，只需增加版本化快照和审核别名，无需改动 ANTLR、Typed AST、Logical IR、Physical IR 与 SQLGlot 后端。

## 6. 复现命令

```powershell
$env:PYTHONPATH = "src"

python scripts/build_curated_scope_alias_snapshot.py `
  --aliases configs/official/external_scope_aliases.json `
  --catalog data/external_catalog/catalog.sqlite3 `
  --runtime configs/official/external_scope_runtime.json `
  --report reports/phase43_curated_scope_alias.json `
  --as-of-date 2026-07-30

pwsh -NoProfile -File scripts/load_external_catalog_doris.ps1

python -m findsl.cli official-coverage-funnel `
  --workbook "D:\path\to\选股提槽实例.xlsx" `
  --json-output reports/phase43_external_scope_funnel.json `
  --report-output reports/phase43_external_scope_funnel.md

python scripts/extract_external_scope_targets.py `
  --funnel reports/phase43_external_scope_funnel.json `
  --output reports/phase43_true_remaining_scope_targets.json

python scripts/audit_funnel_delta_doris.py `
  --previous reports/phase41_external_scope_funnel.json `
  --current reports/phase43_external_scope_funnel.json `
  --json-output reports/phase43_external_scope_delta_doris_audit.json `
  --report-output reports/phase43_external_scope_delta_doris_audit.md `
  --repeats 3 --timeout-seconds 30 --performance-target-ms 10000
```
