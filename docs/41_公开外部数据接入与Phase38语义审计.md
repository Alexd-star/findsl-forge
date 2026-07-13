# 公开外部数据接入与 Phase 38 语义审计

## 1. 本阶段结论

本阶段没有把“尽可能多生成 SQL”当成唯一目标，而是同时检查数据来源、集合含义和 Doris 实际执行结果。官方工作簿共有 5799 条问句，旧严格成功集为 1097 条。当前新架构后端成功 976 条，其中旧严格成功集迁移 947 条，迁移率为 86.33%。剩余严格缺口不再混有普通编译器异常，主要是没有可靠成员关系的自由文本范围，以及少量只有指数成员、没有指数自身行情的 `queryData` 标量问题。

本轮接入新浪公开板块 290 个，包含 175 个概念、31 个地域和 84 个行业，全部板块均取得非空成员集合。该快照新增 21297 条范围成员关系和 5160 条行业关系。随后接入 AKShare 公开指数目录与成分接口，补齐上证周期、380 稳定、上证上游、上证指数、科创 50 等语义明确的指数范围。Doris 当前实际装载 61862 条范围成员关系、28386 条行业关系和 5686 条交易规则，Stream Load 过滤行数均为零。

## 2. 数据边界

| 数据域 | 来源 | 当前用途 | 可信边界 |
|---|---|---|---|
| 官方日行情与衍生行情 | 赛题方三张 Doris 表 | 指标、窗口、事件和结果输出 | 作为比赛核心事实表 |
| 概念、行业和地域成员 | 新浪、东方财富及审计别名快照 | 范围过滤、集合交并差 | 明确标记第三方来源和快照日期 |
| 指数定义与成分 | 中证、国证、AKShare 公开接口 | 指数范围过滤 | 成分来源与指数行情来源分开记录 |
| 行业归属 | BaoStock CSRC 分类 | `belong_industry` 单值行业基准 | 不与概念板块混用 |
| T+0 规则 | 上交所、深交所、北交所规则 | 交易品种规则筛选 | 规则表不代替分时成交数据 |
| 指数日行情 | AKShare/Sina | 指数 `queryData` 标量 | 统一锚定官方行情最大日期，禁止未来数据穿越 |

第三方成员关系进入独立的 `findsl_ext` 数据库。编译器生成 SQL 时同时固定 `snapshot_id` 和 `scope_code`，因此同名板块更新后不会悄悄改变旧证据。SQLite 原始目录、Doris 导出清单和 runtime JSON 各自承担抓取归档、执行装载和编译期解析职责，三者可以通过快照编号追溯。

## 3. 本轮修正的错误

旧同步逻辑曾先删除“公司、行业、指数”等后缀，再判断名称是否相等。这种方法适合生成搜索候选，却不适合直接确认金融集合。例如“金融公司”在归一化后与“金融指数”都变成“金融”，由此产生的 SQL 虽然可以执行，筛选范围却已经被替换。本轮将指数匹配收紧为三种情况：数据源名称逐字一致；问句明确包含“指数”；配置文件记录了经过审核的指数代码映射。

规则收紧后主动撤回 7 条旧成功，包括金融公司、部分泛化行业词和水电等未经确认的指数替代。与此同时，公开指数数据新增 9 条可执行问句。因此表面净增只有 2 条，但可靠集合扩大了，旧的错误证据也被移除。这个变化应在答辩中如实说明：项目追求的是可解释的正确率，不是用宽松模糊匹配堆成功数量。

真实 Doris 审计还发现了一个独立的 renderer 缺陷。问句“上证周期中最新价下穿 24 日均线”已经在 Physical IR 中包含 `lastPx`，但前缀和 CTE 只输出证券主键与均线值，事件表达式随后引用了 CTE 外部不存在的 `q.lastPx`。修复后，前缀 CTE 会透传输入计划所需的普通字段，事件表达式统一引用 `prefix_values.lastPx`，外层范围与日期约束再重定向到 `event_rows`。对应 SQL 已在真实 Doris 上执行通过。

## 4. 真实执行结果

新浪数据带来 3 条新增成功，Doris 审计为 3/3 通过。公开指数数据带来 9 条新增成功，修复 renderer 后 Doris 审计为 9/9 通过。每条 SQL 重复执行 3 次，行数和结果哈希保持一致，执行时间均低于 10 秒。Phase 38 指数增量审计中，最高 P95 约为 85.3 ms；该数字来自当前本地 Doris 数据规模和热缓存环境，不外推为生产集群 SLA。

空结果只能证明 SQL 可以正确执行，不能单独证明金融条件语义正确。因此本阶段同时保留非空场景，例如 380 稳定指数成员返回 190 条、上证上游排名返回 5 条、上证周期与 AIGC 并集条件返回 31 条。所有执行报告均保存 SQL 哈希、结果哈希、行数、耗时和错误字段，便于复现。

## 5. 仍未补齐的范围

剩余名称中，一部分是公开数据源可以继续补齐的标准概念，例如低空经济、储能、DeepSeek、可控核聚变和脑机接口。同花顺公开页面当前对自动分页触发限流，项目已经加入逐概念缓存、失败后继续和显式代理控制，但本轮没有取得任何完整新概念，因此没有导入半截数据。

另一部分名称没有统一行业标准，包括 S 板、深海科技、英美贸易业、擒牛火箭、腾讯霸主等。还有些词可能是错别字、临时题材或用户自定义组合，如 `msic`、`谷子cop`、`破镜`。这类范围不能靠字符串相似度自动指定成员。若赛题方确认其标准名称或给出成员表，现有 provider 和 runtime 机制可以直接接入；在此之前，编译器继续返回 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`。

公司范围也不能与概念范围混淆。例如“摩尔线程”可以按证券身份解析，而“摩尔线程概念”应代表关联公司集合；“京东方”同时对应 A/B 股，不能在没有代码的情况下任选一只。港股公司和海外指数若不在官方 A 股事实表中，即使取得外部成员，也无法凭空构造官方行情字段。

## 6. 复现命令

```powershell
python scripts/sync_sina_sectors.py --catalog data/external_catalog/catalog.sqlite3 --cache data/external_catalog/sina_cache_2026-07-13 --report reports/sina_sector_sync.json --as-of-date 2026-07-13 --require-complete
python scripts/sync_official_index_catalog.py --targets configs/official/external_scope_targets.json --catalog data/external_catalog/catalog.sqlite3 --report reports/official_index_catalog_sync_phase37.json --as-of-date 2026-07-13
powershell -ExecutionPolicy Bypass -File scripts/load_external_catalog_doris.ps1
python scripts/audit_funnel_delta_doris.py --previous reports/phase37_sina_external_funnel.json --current reports/phase38_public_index_funnel.json --json-output reports/phase38_public_index_delta_doris_audit.json --report-output reports/phase38_public_index_delta_doris_audit.md --client mysql --host 127.0.0.1 --port 9030 --user root --database newzl --repeats 3
```

## 7. 后续优先级

第一优先级是等待限流窗口恢复后续跑同花顺缓存，或接入具有明确授权和版本日期的概念成分源。第二优先级是为剩余名称建立“标准实体、疑似别名、自由文本、非 A 股对象、需赛题方确认”五类审计表。第三优先级是为新增非空问句编写独立参考 SQL并比较完整行集，而不只验证生成 SQL 能运行。任何新增成功都必须经过 runtime 来源检查、SQLGlot 校验、真实 Doris 执行和证据刷新四道门。
