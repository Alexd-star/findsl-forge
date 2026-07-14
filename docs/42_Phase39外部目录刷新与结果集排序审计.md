# Phase 39 外部目录刷新与结果集排序审计

## 1. 阶段结论

本阶段在不修改赛题方三张事实表的前提下，刷新了公开板块成员目录，并将第三方关系继续隔离在 `findsl_ext` 数据库。官方工作簿仍为 5799 条问句，旧严格成功集为 1097 条。新架构当前后端成功 983 条，其中旧严格成功集迁移 954 条，迁移率从 Phase 38 的 86.33% 提升到 86.96%。剩余 143 条严格缺口包括 141 条范围成员关系不可用和 2 条指数自身行情标量不可用。

新增的 7 条严格迁移问句覆盖算力、液冷、低空经济、人脑工程等集合组合。它们均经过 ANTLR4 前端、Typed AST、Logical IR、优化器、Physical IR、SQLGlot Doris AST 和后端安全校验，并在真实 Doris 上重复执行。该结果只说明这 7 条新增 SQL 已通过本轮执行与稳定性审计，不把 983 条后端成功直接宣称为全部完成，更不把 5799 条总语料当作 SQL 正确率分母。

## 2. 外部目录刷新结果

2026-07-15 东方财富定向同步共发现 991 个公开板块，其中 75 个与配置目标或经过审核的别名匹配。当前完整抓取 48 个板块，形成 7113 条范围成员关系和 1341 条行业成员关系；另有 27 个板块在请求过程中被上游关闭连接，177 个自由文本目标没有匹配到标准同名板块。失败板块未用前五页、估算成员或空集合替代，旧版本快照也没有被删除。

SQLite 目录目前包含 16 个版本化快照。导出并装载 Doris 后，`findsl_ext.scope_membership` 为 68975 行，`industry_membership` 为 29727 行，`instrument_rule` 为 5686 行，三张表的 Stream Load 过滤行均为 0。指数行情表维持 14533 行。本轮新增快照和旧快照通过 `snapshot_id` 并存；编译器运行时目录按同一来源、范围代码选择最新日期，生成 SQL 同时固定 `snapshot_id` 与 `scope_code`，避免把历史成员和当前成员混成一个不可追溯集合。

## 3. 网络与采集器修正

原提供方固定访问 `29.push2.eastmoney.com`。实际排查表明，同一查询在不同公开分片上的可用性并不一致，单一主机失败不能推出板块无数据。采集器因此加入同源分片故障转移、逐请求原始响应缓存、超时与退避参数、可选系统 curl 兜底和显式代理控制。只有完整分页全部返回后才构造快照，失败信息保留端点和异常原因。

系统 curl 兜底只在提供方自行创建 HTTP 会话的生产路径中自动启用。测试或调用方显式注入会话时，除非同时注入 curl loader，否则不会访问网络。这样既保留 Windows Schannel 与 VPN 环境下的恢复能力，也保证单元测试是可重复的纯离线测试。当前网络窗口中，27 个板块在所有候选分片上仍被主动断开，因此报告保持 `source_complete=false`，没有把偶发的单次成功写成稳定来源能力。

同花顺路径也进行了复核。9 个已知概念均只能取得前 5 页，后续分页受反爬限制，没有任何概念形成完整成员集。同步程序返回失败，没有导入半截数据。后续若上游恢复，现有逐页缓存可从断点继续；若长期不可用，应选择具有明确来源、版本日期和使用边界的替代数据，而不是把前 5 页当作全量。

## 4. 别名策略

本轮只登记能够由标准板块名反证的候选别名，例如 `deepseek相关 -> DeepSeek概念`、`hbm -> 高带宽内存`、`专精特新小巨人企业 -> 专精特新`、`智能城市 -> 智慧城市`。`msic` 被记录为对 `MSCI中国` 的显式拼写纠正候选。别名只有在对应板块完整抓取并生成版本化成员关系后才会进入运行时目录；本轮上游未返回这些板块的完整分页，因此它们没有带来虚假成功。

`科技`、`金融公司`、`S板`、`英美贸易业`、`擒牛火箭` 等含义不唯一或没有标准成员表的文本继续拒绝。系统不会因为字符串相似就把“金融公司”改成“金融指数”，也不会把公司、概念、行业和指数四类对象互相替换。

## 5. Doris 差量审计

Phase 39 相对 Phase 38 新增 7 条后端成功，真实 Doris 审计为 7/7 通过。每条查询重复执行 3 次，结果行数分别为 10、5、27、5、205、1 和 576；最高一次冷启动耗时为 1466.833 ms，全部低于 10000 ms 目标。第二次独立复核再次执行每条查询 2 次，7 个结果 SHA-256 与第一次规范化审计逐条一致。

审计过程中发现，旧差量脚本直接按 MySQL 客户端返回顺序做流式哈希。SQL 未声明 `ORDER BY` 时，Doris 可以用不同顺序返回同一个集合，因此跨会话哈希可能变化，不能据此判定数据改变。修正后的审计器使用 SQLGlot 分析最外层查询：已有排序时沿用生成 SQL 的顺序契约；没有排序且没有 `LIMIT` 时，外包一层按全部投影列排序的审计查询；没有排序的 `LIMIT` 查询直接拒绝，因为其结果集合本身不确定。报告同时保存原 SQL 哈希、执行 SQL 哈希和 `canonical_full_row_order` 契约。

## 6. 复现命令

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7897"
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
$env:PYTHONPATH = "src"

python scripts/sync_external_catalog.py --targets configs/official/external_scope_targets.json --catalog data/external_catalog/catalog.sqlite3 --runtime configs/official/external_scope_runtime.json --report reports/external_catalog_proxy_curl_phase39.json --as-of-date 2026-07-15 --trust-environment-proxy --cache-dir data/external_catalog/eastmoney_cache_2026-07-15 --timeout-seconds 15 --max-attempts 1 --request-interval-seconds 0.1 --replace

powershell -ExecutionPolicy Bypass -File scripts/load_external_catalog_doris.ps1

python -m findsl.cli official-coverage-funnel --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/phase39_external_refresh_funnel.json --report-output reports/phase39_external_refresh_funnel.md

python scripts/audit_funnel_delta_doris.py --previous reports/phase38_public_index_funnel.json --current reports/phase39_external_refresh_funnel.json --json-output reports/phase39_external_refresh_delta_doris_audit.json --report-output reports/phase39_external_refresh_delta_doris_audit.md --client mysql --host 127.0.0.1 --port 9030 --user root --database newzl --repeats 3
```

## 7. 尚未补齐的内容

剩余 141 条范围缺口中仍混有三类问题：可以继续从标准公开目录补齐的概念或行业；需要明确拼写或实体类型的疑似别名；没有统一行业定义的用户自定义题材。第一类可继续通过版本化 provider 接入，第二类必须保留人工审核记录，第三类需要赛题方给出成员表或确认允许采用某一指定第三方口径。

另外两条 `上证指数` 相关问句缺少的是指数自身日行情标量，不是指数成分。成员表只能回答“哪些证券属于指数”，不能回答“指数当日涨跌幅是多少”。现有 `index_quote` 已具备独立资源和快照约束，下一步应检查这两条问句所需日期是否落在当前 14533 行指数行情覆盖范围内；若缺日期，可从同一公开指数行情源补齐，不能拿成分股平均值冒充指数涨跌幅。

