# Phase 47 大盘基准政策与跨资源日历对齐

## 1. 阶段结论

本阶段处理旧严格成功集中最后三条非范围类缺口。三条 DSL 都使用 `queryData('', '大盘', ...)`，分别比较今天涨跌幅、今天涨幅和近一月涨跌幅。官方提槽说明明确指出，`queryData` 的 `keywords` 可以是股票、行业、概念或指数，因此把“大盘”作为一个具有自身行情的基准标的是符合 DSL 函数边界的；但规范没有继续规定“大盘”唯一对应上证综指、沪深300或其他宽基指数。

系统没有把该歧义写死在规划器分支中，而是新增版本化基准政策目录。当前项目业务口径将无市场限定的“大盘”映射为沪深300 `000300`，政策 ID 为 `a-share-broad-market-v1`。深交所发布资料将沪深300描述为能够充分代表沪深市场股价变动情况、反映市场整体走势的重要指标，这为默认选择提供了公开依据；该依据仍不等于赛题方唯一口径，所以报告、配置和答辩材料都明确称其为“项目业务政策”。若赛题方指定中证全指、上证综指或其他指数，只需替换政策目录并装载对应版本化行情，不需要修改编译器各层。

实施后，旧严格成功集迁移由 `1019/1097` 提升到 `1022/1097`，迁移率为 `93.16%`；5,799 条工作簿中的新后端成功数由 1,050 提升到 1,053。剩余 75 条严格缺口全部为范围成员数据或范围名称无法唯一证明，不再混有普通标量规划错误。

## 2. 版本化基准政策

`configs/official/benchmark_policy.json` 保存别名、市场上下文、指数代码、指数名称、政策 ID、来源、生效日期和依据链接。运行时 `BenchmarkPolicyCatalog` 先查找市场精确项，再查找无市场默认项；零命中或多命中都返回确定性失败，不靠列表顺序静默挑选。规划器只有在 `queryData` 的范围是单个原子时才尝试该政策，成功后仍需从 `external_index_quotes.json` 取得已验收的行情快照。如果政策指向的指数没有版本化行情，系统返回 `PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE`，不会生成缺表 SQL。

当前绑定的沪深300行情快照为 `akshare-sina-index-2026-07-15-42e29790031f`，覆盖 2002-01-04 至 2026-07-14。物理计划同时固化 `index_code='000300'` 和该 `snapshot_id`，因此同一代码的另一批数据不会在不知情时改变结果。政策与行情快照分开管理：前者回答“大盘指谁”，后者回答“使用哪一版指数行情”，这比在别名表中只存一个字符串更适合生产审计。

## 3. 跨资源时间错位根因与修复

真实 Doris 预检发现，官方股票基本行情表最新日期为 2026-04-14，外部指数行情表最新日期为 2026-07-14。原有显式指数路径在处理“今天”时，会对两张表分别执行 `MAX(bizdate)`。这样生成的 SQL 可以执行，也可能得到稳定结果，但它比较的是不同交易日，属于原理性错误，而不是性能或数据缺失问题。

修复后的时间约束保留“被过滤列属于外部指数表”，同时把相对日期的日历锚点切换到 `official_basic`。`PhysicalLatestValue` 和 `PhysicalNthLatestValue`读取官方行情日历；`PhysicalRecentSessions`、`PhysicalDynamicDateRange`与`PhysicalSessionBoundaryRange`新增可选的 `anchor_resource_id`，外部表的日期列使用官方日历计算出的边界。无日期标量同样取官方最新交易日。由此，“今天”的股票和指数都落在 2026-04-14，“近一月”也共享同一个起止窗口。

这项修复不仅服务“大盘”别名。已有的上证指数、沪深300、深证成指显式 `queryData` 路径也会获得相同的日历一致性，避免外部数据刷新快于官方赛题数据时产生未来信息穿越。新增回归测试分别覆盖今天、近一月和无日期场景，并检查 SQL 的日历子查询来自 `newzl.hsj_stock_hq_basic`。

## 4. Doris 独立证据

增量审计从 Phase 46 与 Phase 47 漏斗中自动提取三条新增成功问句，每条在真实 Doris 上执行五轮。三条均在 10 秒门禁内完成，结果哈希跨轮稳定；近一月涨跌幅与 60 日均线场景返回 786 行，另外两条在当前数据快照上为空。增量执行只能证明 SQL 可执行、结果稳定和性能达标，空结果本身不能证明业务语义正确。

为补足这一证据缺口，`collect_phase47_benchmark_policy_evidence.py`独立写出三套参考 SQL。参考查询直接读取沪深300锚点日涨跌幅，单独计算 AI 范围内的稳定并列处理排名，单独计算近一月股票与指数的末值，并在最新日连接 60 日均线。它没有复制编译器生成 SQL 的 `INTERSECT` 或命名标量结构。三套参考查询与生成 SQL 的完整 `(mktcode,tgtcode,bizdate)` 行集哈希全部一致，结构合同和性能门禁也是 `3/3 PASS`。最高 P95 约 1.67 秒，来自首次冷执行；热执行约为几十毫秒。

证据文件包括：

- `phase47_benchmark_policy_funnel.json/md`：5,799 条官方工作簿迁移漏斗；
- `phase47_benchmark_policy_delta_doris_audit.json/md`：三条新增成功问句的重复执行证据；
- `phase47_benchmark_policy_doris.json/md`：独立参考 SQL、完整行集哈希、EXPLAIN 摘要和政策来源合同。

## 5. 评分价值与边界

本阶段直接增强正确性、可解释性、可维护性和现场抗质疑能力。评委若问“为什么大盘是沪深300”，可以展示公开依据和版本化政策，同时明确这是可替换业务约定；若问“指数数据比股票数据新怎么办”，可以展示统一日历锚点与 2026-04-14 的真实证据；若问“结果是否只是能跑”，可以展示三套独立参考 SQL 的完整哈希一致性。

这里不宣称赛题方已经确认“大盘=沪深300”。配置化政策把“系统具备能力”与“业务方最终选定口径”分开：当前交付可运行、可复现，也允许赛题方在不改编译器的情况下替换口径。剩余 75 条范围缺口仍需逐项取得完整成员快照或唯一可证明映射；本阶段没有用字符串相似度、单成员替代或伪造空表来追求表面上的 `1097/1097`。

## 6. 复现顺序

```powershell
$env:PYTHONPATH = "src"

python -m findsl.cli official-coverage-funnel `
  --workbook "D:\path\to\选股提槽实例.xlsx" `
  --json-output reports/phase47_benchmark_policy_funnel.json `
  --report-output reports/phase47_benchmark_policy_funnel.md

python scripts/audit_funnel_delta_doris.py `
  --previous reports/phase46_derived_scope_funnel.json `
  --current reports/phase47_benchmark_policy_funnel.json `
  --json-output reports/phase47_benchmark_policy_delta_doris_audit.json `
  --report-output reports/phase47_benchmark_policy_delta_doris_audit.md `
  --repeats 5 --performance-target-ms 10000

python scripts/collect_phase47_benchmark_policy_evidence.py `
  --repeats 5 --performance-target-ms 10000
```

核心实现位于 `src/findsl/official/external/runtime.py`、`src/findsl/official/physical/planner.py`、`src/findsl/official/physical/ir.py`与`src/findsl/official/backend/doris.py`。
