# Phase 46 派生范围与中证快照生命周期修复

## 1. 阶段结论

本阶段处理三条能够由现有受控数据直接证明的严格迁移缺口：`科创板注册制`、`沪深主板注册制`和`当天买当天卖`。前两项不是外部概念板块，而是可以由交易所市场代码与证券代码段确定的市场范围；后一项不依赖猜测证券名单，直接读取已经版本化的 `instrument_rule.t0_eligible`。因此，这三项进入编译器内部的派生范围规则，与公开概念、指数成员和人工审核别名保持分层。

最终旧严格成功集迁移由 `1016/1097` 提升到 `1019/1097`，迁移率为 `92.89%`；5,799 条完整工作簿中的新后端成功数由 1,047 提升到 1,050。剩余严格缺口为 75 条范围数据不可用和 3 条非单值 `queryData('大盘', ...)`，没有普通 SQL 生成异常混在其中。这里的 92.89% 是旧严格成功集迁入新架构的比例，不是对全部训练语料宣称 92.89% 准确率。

## 2. 派生范围实现

范围解析原来只认识两类对象：官方证券名称目录和外部成员目录。新增规则虽然已经能够下推为代码范围或交易规则半连接，但字段收集阶段会先把它们误判为成员数据缺失。本阶段在预解析层增加 `derived_market` 与 `instrument_rule` 两种受控解析结果，使资源检查、字段收集和最终下推共享同一语义分类，同时避免把交易所规则伪装成第三方板块。

`科创板注册制`复用现有科创板范围，即上海市场 `mktcode=1` 与 `688000-688999` 代码段。`沪深主板注册制`复用沪市主板和深市主板并集，覆盖已经测试的 `600/601/603/605` 与 `000/001/002/003` 代码段。这些规则只表达当前证券所属交易板块，不声称恢复某只证券历史上采用的发行审核制度。

`当天买当天卖`读取 `findsl_ext.instrument_rule`，按稳定证券键、快照 ID 和 `t0_eligible=TRUE`生成 `EXISTS` 半连接。当前版本化 A 股规则目录中合资格成员为 0，因此真实结果为空。空结果来自规则数据，不是 `1=0`、固定空表或异常吞掉。物理谓词归一化还消除了范围槽与“是否T+0”指标槽产生的重复半连接，Doris EXPLAIN 从两个规则表半连接收敛为一个。

## 3. 中证快照修复

首次差量执行时，“沪深300沪市指数与沪深主板注册制交集”的行业均值样例返回 0 行。进一步检查发现，运行中的中证 `000972` 快照只有 1 条成员，而且市场代码为深圳；这与 `300沪市`的定义不相符。直接读取中证指数官方成分文件后，`000972cons.xls`共有 189 条记录，文件列名为当前中英双语格式，全部属于上海市场。

项目随后使用带 `expected-count=189` 的定向同步器重新导入 `000972`，生成 `csindex-2026-07-30-ba167bb7985c`。修复后同一官方问句返回 61 行，完整结果集与独立参考 SQL 一致。官方文件地址为：

- `https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000972cons.xls`
- `https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000300cons.xls`

同步过程中又发现一个目录生命周期缺陷：定向同步原来按“来源 + 日期”整体替换，会在导入 `000972` 时删除同一天已经验收的 `000300`。本阶段把定向同步改为只替换相同快照 ID，并新增同日双指数并存测试。随后重新导入 `000300` 的 300 条官方成分，重建审核别名快照。最终运行时目录同时选择 `000300` 的 300 条快照和 `000972` 的 189 条快照，二者不再互相覆盖。

## 4. Doris 语义与性能证据

普通差量审计对新增三条问句各执行五轮，检查完整输出哈希稳定与 10 秒性能阈值，结果为 `3/3 PASS`。两条非空问句分别返回 61 行和 582 行；最终一轮最高 P95 约 0.39 秒。

为了避免“能执行”被误写成“语义正确”，本阶段新增独立参考 SQL 审计。参考查询没有复制编译器 SQL，而是分别手写最新行情与 T+0 规则半连接、中证 000972 与主板范围内的行业平均总市值 CTE、科创板范围内的行业最小总市值 CTE。三套参考查询与生成 SQL 的完整 `(mktcode,tgtcode,bizdate)` 行集哈希均一致，结构片段和性能门禁同样为 `3/3 PASS`。

外部目录重新装载后，Doris 中 `scope_membership` 为 207,268 行、`industry_membership` 为 40,907 行、`instrument_rule` 为 5,686 行，Stream Load 过滤行均为 0。全量测试收集并通过 1,022 项，Ruff 全仓通过。

## 5. 剩余边界

本阶段以后仍有 75 条严格范围缺口，涉及 68 个未解析原子，主要是 `S板/s板/s版`、`深海经济`、`科技`、数字型自定义板块、策略黑话、基金或海外主体。它们不是统一的代码缺陷：有些缺成员数据，有些名称可对应多个公开分类，有些不是 A 股证券范围，还有些只有策略作者才能解释。系统继续返回 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`，不会根据编辑距离自动选择一个相似板块。

三条 `queryData('', '大盘', ...)`也继续拒绝。当前范围语义中的“大盘”是 199 只大盘股成员，而标量查询没有给出 `AVG/SUM/MAX/MIN`。市场实务中“大盘”可能指上证综指、沪深300或其他基准，缺少赛题方口径时不能静默选择其中之一。生产化方案应增加显式 benchmark policy，由业务方把别名、指数代码、行情快照和生效日期一起版本化；在该政策确认前，拒绝比隐式平均更可靠。

## 6. 复现顺序

```powershell
$env:PYTHONPATH = "src"

python scripts/sync_csindex_constituents.py --code 000972 --name "300沪市" `
  --full-name "沪深300沪市指数" --catalog data/external_catalog/catalog.sqlite3 `
  --runtime configs/official/external_scope_runtime.json `
  --report reports/phase46_csindex_000972_sync.json --as-of-date 2026-07-30 `
  --expected-count 189 --trust-environment-proxy

python scripts/sync_csindex_constituents.py --code 000300 --name "沪深300" `
  --full-name "沪深300指数" --catalog data/external_catalog/catalog.sqlite3 `
  --runtime configs/official/external_scope_runtime.json `
  --report reports/phase46_csindex_000300_restore.json --as-of-date 2026-07-30 `
  --expected-count 300 --trust-environment-proxy

pwsh -NoProfile -File scripts/load_external_catalog_doris.ps1

python -m findsl.cli official-coverage-funnel --workbook "D:\path\to\选股提槽实例.xlsx" `
  --json-output reports/phase46_derived_scope_funnel.json `
  --report-output reports/phase46_derived_scope_funnel.md

python scripts/collect_phase46_derived_scope_evidence.py --repeats 5 `
  --performance-target-ms 10000
```

完整证据见 `submission_artifacts/evidence_snapshots/phase46_*`。核心实现位于 `src/findsl/official/physical/planner.py`，同步生命周期修复位于 `scripts/sync_csindex_constituents.py`。
