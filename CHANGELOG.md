# CHANGELOG

本文档记录 FinDSL Forge 的重要变更。详细提交历史以 Git 为准，提交包证据以 `submission_artifacts/evidence_snapshots/` 为准。

## 2026-06-10

### 官方 DSL 语义补强

- 支持 `rank(..., agg_func, count_exp)`，将聚合排名编译为时间桶聚合、桶内 `ROW_NUMBER()` 排名和 `CONS/EXIST` 命中桶统计。
- 支持 `cross_above/cross_down/golden_cross(..., count_exp)`，将上穿、下穿和金叉编译为基于 `LAG()` 的每日事件行，再交给统一 `count_exp` 逻辑统计。
- 修正穿越事件窗口语义：`LAG()` 源数据保留目标窗口开始日前的历史行，事件次数只在 `event_rows.bizdate` 目标窗口内统计，避免漏判窗口首日上穿/下穿/金叉。
- 补充 `涨停价`、`跌停价` 官方指标别名，分别映射到 `upSealPx`、`downSealPx` 并沿用价格单位换算。
- 补强官方口语日期归一化，覆盖 `过去20天`、`30个交易日`、`三个月之内`、`近半年`、`近5个月至今`、`2024年8月`、`9号`、`九月十五号`、`本季度` 等表达。
- `count_exp` 表达式比较支持同义日期 scope：当两个日期槽能无 warning 归一到同一日期窗口时，可以在同一个计数比较中使用。
- 官方 workbook 覆盖刷新为 `5,792/5,799` 可解析、`1,872` 条可落地编译，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 降至 `15`。

### 官方真实数据与 Doris 证据

- 完成官方三张 CSV 在本地 Apache Doris 中的真实落库核验：`hsj_stock_code_info=5686`、`hsj_stock_hq_basic=13650347`、`hsj_stock_hq_ext=6170822`。
- 修正官方 schema 中 `lastPx/preClosePx` 真实空值处理，避免 Stream Load 过滤或失败。
- 将官方 Stream Load 默认路径调整为宿主机直连 BE `8040`，并显式使用 `Expect: 100-continue`、`strict_mode:false`、`max_filter_ratio:0` 和长超时。
- 将 `hsj_stock_hq_basic_technical` 构建从单次大 INSERT 改为 `mktcode + tgtcode hash bucket` 分片构建，解决单 BE Docker 环境下的内存 OOM。
- 新增 `scripts/prepare_official_doris_evidence.ps1`，统一完成官方文件检查、Doris 就绪检查、落库、特征表构建、行数验收、SQL/EXPLAIN 证据和 Markdown/JSON 报告生成。
- 新增 `deploy/doris/official/05_technical_features_by_market.sql`，用于按市场和 hash bucket 构建长周期技术特征。
- 生成官方 Doris 证据报告，确认三张派生特征表均为 `13650347` 行，并在报告生成前强制校验 baseline/prefix 行数一致。
- 新增 `docs/22_官方真实数据落库复盘与满分冲刺计划.md`，记录真实数据分析、根因修复、证据结果、剩余短板和后续冲刺计划。

## 2026-06-07

### 文档整理

- 新增 `PROJECT_INDEX.md`，统一说明项目目录、核心文件、运行入口、历史文件和维护建议。
- 新增 `docs/01_项目简介.md` 至 `docs/17_项目交付说明.md`，建立中文编号文档体系。
- 新增 `archive/README.md`，说明历史归档目录使用规则。
- 在 `README.md` 增加中文文档体系和文件索引入口。

### 语义与验证修复

- 将 `rank(percent=...)` 的百分比阈值 SQL 从近似 `CAST` 写法改为 Doris 官方 `CEIL()` 函数。
- 在 SQLite 本地执行器中注册 `CEIL`，保证本地等价验证可执行 Doris 方言 SQL。
- 修复 reference oracle 中 `OR` 对 `NULL/UNKNOWN` 的三值逻辑处理，补充稀疏辅助表回归测试。
- 保持 `CONS/EXIST`、比较运算、percent rank 与 SQL/Doris 语义一致。
- 补强 Doris SQL validator 的表引用解析，支持反引号表名和库名限定表名，避免未知表通过 `` `table` `` 或 `db.table` 写法绕过检查。
- 新增 SQL validator 和 evidence metadata 回归测试，本轮审计后全量测试数为 197。

### 提交证据

- readiness 证据显示 required gates 全部通过，warning count 为 0。
- 官方风格正例、负例、SQL/reference 等价、Doris 资产完整性和提交包检查均纳入门禁。
- 新增 `src/findsl/evidence_metadata.py` 与 `python -m findsl.cli evidence-metadata`，自动从提交证据快照中抽取门禁、pytest、官方套件和 Doris 加速指标，生成 `submission_artifacts/evidence_metadata.json` 与 `submission_artifacts/evidence_summary.md`，降低技术报告、答辩材料和 Demo 指标之间的人工口径漂移风险。

## 2026-05 至 2026-06

### 核心能力建设

- 实现 DSL 词法、语法、AST、语义校验和 Doris SQL 生成链路。
- 支持 `filter`、`then`、`rank`、`date_between`、`CONS`、`EXIST`、`MA`、`SUM`、`MAX`、`MIN`、`RET` 等主要算子。
- 实现 prefix-sum 长窗口优化、Doris DDL 生成、Doris evidence 采集、Web Demo、NL2DSL 模板和 LLM 候选安全适配。
- 建立 Pandas reference oracle、SQLite 执行器、官方风格测试、readiness 报告和 submission artifacts。

## 版本说明

当前 `pyproject.toml` 中项目版本为 `0.1.0`。该版本是比赛原型/提交版本，不代表商业生产版本。若后续进入长期维护，建议按 `0.2.0`、`0.3.0` 或 `1.0.0` 方式维护语义版本，并在本文档中记录每次变更范围、测试结果和证据快照。
