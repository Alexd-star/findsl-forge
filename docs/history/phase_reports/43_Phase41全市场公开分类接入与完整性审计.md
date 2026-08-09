# Phase 41 全市场公开分类接入与完整性审计

## 1. 阶段结论

Phase 41 将外部范围数据从“按赛题词条逐板块抓取”扩展为“按全市场证券反向汇聚分类关系”。系统以版本化证券身份快照为输入，调用百度股市通公开 related-block 接口，读取每只证券所属的概念、申万行业层级和地域板块，再按来源代码重建成员集合。该路径不修改赛题方提供的三张行情事实表，所有第三方关系仍隔离在 `findsl_ext` 数据库，并由 `snapshot_id` 固定来源和日期。

本轮完整请求 `5529` 只证券，返回并校验 `5529/5529`，形成 `117908` 条范围成员和 `11057` 条行业层级记录。叠加既有公开来源和 39 条人工审核别名后，Doris 中共有 `193168` 条范围成员、`40784` 条行业成员和 `5686` 条交易规则，三张表 Stream Load 的过滤行均为 0。官方 5799 条工作簿中，新后端成功数升至 `1000`；旧严格成功集迁移 `971/1097`，迁移率为 `88.51%`。与 Phase 40 的 `956/1097` 相比，净增 15 条严格成功。

## 2. 为什么改为证券侧反向汇聚

逐板块抓取依赖每个网站的分页页面。同花顺公开页面对大板块只允许稳定取得前 5 页，部分概念实际有几十到一百多页；把前 5 页导入会制造“看似有数据、实际漏成员”的假完整结果。东方财富板块接口也会在不同公开分片上偶发断开，适合通过缓存和分片故障转移补齐已知板块，但不适合把任意自由文本直接猜成标准板块。

证券侧接口一次最多接收 20 只证券，却会为每只证券返回完整的行业、概念和地域列表。只要请求证券集合来自版本化全市场身份快照，并要求每个批次的返回键与请求代码完全一致，就能把数据完整性从“网页是否翻完”转成可程序验证的集合相等条件。同步器因此固定 20 只的源端上限，少返回一只即拒绝整个批次；原始 JSON 按证券代码集合的 SHA-256 原子缓存，网络中断后只重跑缺失批次。

## 3. 数据模型与来源约束

`BaiduRelatedBlockProvider` 把接口返回值解析为三类强类型范围：`concept`、`industry` 和 `region`。来源代码保留为 `BAIDU:<code>`，成员键统一为 `(mktcode,tgtcode)`。申万一级、二级等描述同时进入 `industry_membership.industry_level`，不会把多个行业层级压成一个无来源文本。

快照 `baidu-related-block-2026-07-15-a4e417e5272b` 的内容摘要为 `a4e417e5272b5a9eedf2d3055ffd9396f95607fbb8507d5dcb88399377112f8e`。同步报告保存身份来源、身份快照、请求证券数、返回证券数、各范围类型行数和目录总计。运行时清单只保存可解析的范围名称、来源、日期和快照标识；真正成员仍在 Doris 关系表中查询，不把数万成员展开进生成 SQL。

## 4. 完整性与版本治理修正

本轮补上两处此前容易被忽略的生产风险。第一，东方财富分页器原先遇到空页会直接结束，即使上游声明的 `total` 尚未取满。现在只要实际行数小于声明总数，分页器就抛出稳定异常，不再返回部分集合。第二，同一来源同一天重新生成不同摘要的快照时，旧快照过去会继续留在目录中，撤回错误别名后仍可能被运行时命中。目录现支持 `replace_source_date=True`，在一个 SQLite 事务中删除同源同日旧快照及其成员、别名后再导入新快照，历史日期不受影响。

人工别名继续采用白名单，不做模糊字符串自动上线。新增别名包括 `HBM -> 高带宽存储器HBM`、`MSCI -> MSCI概念`、`豆包 -> 豆包概念`、`储能 -> 储能概念` 等可由公开标准名称反证的关系。`科技`、`大盘`、`S板`、`金融公司`、`SHEIN` 以及数字型自定义板块仍不猜测。`抖音公司` 和 `比亚迪类` 按 A 股范围槽解释为产业链概念，并在配置中写明解释政策，便于赛题方口径不同的时候直接撤回。

## 5. 官方工作簿结果

最终漏斗保持官方总语料 `5799`、ANTLR 前端成功 `5792`、Typed AST 成功 `5695`、Logical IR 和优化器成功 `1827`。Physical IR 与 Doris 后端成功均为 `1000`。旧严格成功集为 `1097`，其中 `971` 条已经迁入新 ANTLR/Typed AST/Logical IR/Physical IR/SQLGlot 架构；剩余 `126` 条严格缺口统一为 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`。

剩余缺口涉及 111 个真正未解析的范围原子，出现 184 次。高频项包括 `SHEIN`、`S板`、`深海经济`、`科技`、`大盘`、`公共服务`、`宁夏算力概念` 和若干自定义数字板块。这些名称或缺少统一成员表，或可能对应多个行业、概念、指数和用户自定义板块。继续靠字符串相似度提高覆盖率会降低 SQL 可信度，因此当前保持可解释拒绝。只要赛题方指定分类口径或提供成员表，现有 Provider/Snapshot/Runtime 接口可直接接入，无需修改编译器核心。

## 6. 真实 Doris 差量审计

Phase 41 相对 Phase 40 新增 15 条严格成功，真实 Doris 重复执行审计为 `15/15 PASS`。每条 SQL 执行 3 次；无显式排序且无 `LIMIT` 的查询由 SQLGlot 外包一层，按全部投影列建立规范结果顺序，已有稳定排序的查询保留生成顺序。三次执行的行数和完整结果 SHA-256 均一致，所有查询低于 10 秒性能门槛，最高 P95 为 `1999.431 ms`。

15 条查询中 11 条返回非空结果，行数覆盖 1、3、8、11、32、37、90、140、223 和 877 等不同规模。4 条返回空集合；空结果只证明当前数据和谓词没有命中，不能单独证明语义正确。因此这些范围同时要求底层成员快照非空，且别名能追溯到原始标准范围。审计报告证明生成 SQL 可执行、结果稳定和性能达标，不把它夸大为 5799 条全部语义正确。

## 7. 复现命令

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7897"
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
$env:PYTHONPATH = "src"

python scripts/sync_baidu_related_blocks.py --catalog data/external_catalog/catalog.sqlite3 --runtime configs/official/external_scope_runtime.json --report reports/baidu_related_blocks_phase41.json --identity-source akshare-security-identity --as-of-date 2026-07-15 --cache-dir data/external_catalog/baidu_related_blocks_2026-07-15 --timeout-seconds 20 --max-attempts 3 --backoff-seconds 0.5 --request-interval-seconds 0.05 --trust-environment-proxy --replace

python scripts/build_curated_scope_alias_snapshot.py --aliases configs/official/external_scope_aliases.json --catalog data/external_catalog/catalog.sqlite3 --runtime configs/official/external_scope_runtime.json --report reports/curated_scope_alias_phase41.json --as-of-date 2026-07-15

powershell -ExecutionPolicy Bypass -File scripts/load_external_catalog_doris.ps1

python -m findsl.cli official-coverage-funnel --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/phase41_external_scope_funnel.json --report-output reports/phase41_external_scope_funnel.md

python scripts/audit_funnel_delta_doris.py --previous reports/phase40_index_scalar_funnel.json --current reports/phase41_external_scope_funnel.json --json-output reports/phase41_external_scope_delta_doris_audit.json --report-output reports/phase41_external_scope_delta_doris_audit.md --repeats 3 --timeout-seconds 30 --performance-target-ms 10000
```

## 8. 当前边界

当前结果可以表述为“在现有官方行情事实表和已接入版本化公开关系数据下，旧严格成功集迁移率达到 88.51%，新增范围查询通过真实 Doris 稳定性审计”。不能表述为“5799/5799 全部成功”，也不能把缺少来源的自定义题材硬编码为空集合或全市场。

后续高价值工作不再是继续堆别名，而是等待赛题方确认自定义板块口径，或接入具有合法授权、完整历史版本和成员变更日期的专业关系库。若只能得到当前截面成员，也必须继续把 `as_of_date` 与事实表查询日期的差异写进 warning，避免用 2026 年成员解释历史年份查询而不披露幸存者偏差。
