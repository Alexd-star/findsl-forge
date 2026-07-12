# CHANGELOG

本文档记录 FinDSL Forge 的重要变更。详细提交历史以 Git 为准，提交包证据以 `submission_artifacts/evidence_snapshots/` 为准。

## 2026-07-12

### ANTLR/IR 新后端时序语义

- 新增 SQL 无关的 `TemporalQuantifier`，严格解析 `CONS/EXIST`、比较符、范围、中文数字、`每年/每月/每日`、单位归一和默认阈值，非法合同返回稳定错误码。
- `BoundFunction` 不再把 `count_exp` 作为裸字符串保存；原子时序比较会降低为 `LogicalConsecutive` 或 `LogicalExist`，行谓词保留在时序节点内部，避免先过滤后错误拼接连续段。
- 新增 `PhysicalTemporal` 与交易窗口合同。日粒度 `EXIST` 使用集合聚合，`CONS` 使用完整交易序号与匹配序号之差的岛屿法，不使用自然日 `DATEDIFF`，也不把连续次数近似为窗口总次数。
- SQLGlot Doris 后端新增集合式 CTE 计划：`source_rows/eligible_rows/sequenced_rows/matched_rows/runs/temporal_metrics/qualified`，最终按稳定股票键连接最新行情快照。
- 新增独立 Python 时序 oracle 和 `scripts/collect_phase9_temporal_evidence.py`。官方 13,650,347 行基础表上，最近 10/5 个交易记录的 `CONS=3日`、`EXIST>=5`、`EXIST>0` 和 `CONS=每日` 均实现 Doris/独立 oracle 行集哈希一致 `4/4`，P95 均低于 0.6 秒（以提交快照实际值为准）。
- 日期槽新增 Typed DateConstraint，区分最近 N 个交易记录、最近 N 个日历月/年和显式年份范围；覆盖“这五天”“过去6天”“近3个交易日”“两年内”“近两月”和中文数字年份，不再在物理层猜测原始字符串。
- 新后端迁移覆盖从 `72/1097（6.56%）` 提升至 `95/1097（8.66%）`。Logical IR 数量按严格时序口径重新计算；复合及多时序谓词在独立关系分支完成前明确拒绝，不再以裸字符串进入后续阶段。
- 官方领域证据生成改为隔离 Phase 3 基线并按 750 条分块执行 Phase 4，全量 5,799 条门禁保持不变，同时限制 Windows 开发机和 CI 的峰值内存。
- Doris 版本证据改从 `SHOW FRONTENDS` 获取真实 FE build；`SELECT VERSION()` 的 `5.7.99` 仅标注为 MySQL 协议兼容版本。

## 2026-07-11

### 严格官方编译基线

- 新增 strict/recovery 双模式。strict 不静默修复源码，recovery 返回结构化 repair、warning、fallback 和 degraded 状态。
- 为官方 12 类函数建立精确签名，禁止额外参数被切片忽略，禁止数字、布尔值或表达式冒充字符串槽位。
- 新增官方 AST 类型分析，覆盖数值/布尔/字符串/时间、百分比、四则运算、比较、`between`、`~=` 和裸标识符检查。
- strict compiler 对 repair、warning 和结构化 fallback 统一使用 `OFFICIAL_DEGRADED_SEMANTICS`，CLI JSON 错误路径返回稳定错误码和退出码 2。
- 重建官方 5,799 条工作簿覆盖率：strict parse `5,792`、recovery parse `5,799`、strict compile `1,097`、recovery compile `1,830`、degraded `733`。
- `1=0/1=1` 改为编译器结构化记录，当前分别为 `472/328` 条，不再扫描 SQL 文本，避免误判合法 `WHERE 1=1` 和字符串 `'1=0'`。
- 修正官方 CSV 日期画像，`first_date/last_date` 使用全文件真实最小值和最大值，不再假设 CSV 已按日期排序。
- 新增 `docs/36_严格官方编译基线与口径说明.md`，明确历史 `compile_ok=1,882` 是 recovery 返回口径，不能作为 SQL 正确率。

## 2026-07-06

### 官方真实数据证据与审计口径刷新

- 刷新官方 workbook 覆盖率：语法解析从 `5,792/5,799` 提升到 `5,799/5,799`，可落地 Doris SQL 编译数从 `1,873` 提升到 `1,882`，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 从 `14` 降到 `3`。
- 修复并归档官方 Excel 中 7 条文档噪声样例，覆盖边缘引号、前导 `and`、多余右括号和孤立日期字面量等可判定标点问题；原始输入仍保留在覆盖率报告中用于审计。
- 增强 `count_exp` 解析和 SQL 生成，支持可由日频官方三表解释的区间次数、连续区间、半年度归一到月份桶和 bounded count/run-length 谓词。
- 新增 `python -m findsl.cli official-performance-matrix`，从真实 `reports/official_doris_evidence.json` 生成逐问句性能矩阵；当前 6 条官方 Doris 查询全部满足 P95 <= 10s，最大 P95 为 `61.269 ms`。
- `evidence_metadata.json` 和 `evidence_summary.md` 新增官方逐问句性能矩阵摘要，确保代码、报告、截图和 metadata 引用同一份 evidence。
- 新增 `docs/grammar/OfficialSlot.g4` 与 `docs/34_官方槽位DSL_BNF与ANTLR形式化说明.md`，将官方槽位 DSL 的语法优先级、函数调用、比较、`between`、`limit` 和四则运算形式化。
- 新增 `docs/35_官方三表缺失数据域不可伪造SQL审计报告.md`，逐条说明剩余 3 条 `count_exp` 和 1 条周期函数为什么不能在缺失数据域下伪造 SQL。

## 2026-06-10

### 官方 DSL 语义补强

- 支持 `rank(..., agg_func, count_exp)`，将聚合排名编译为时间桶聚合、桶内 `ROW_NUMBER()` 排名和 `CONS/EXIST` 命中桶统计。
- 支持 `cross_above/cross_down/golden_cross(..., count_exp)`，将上穿、下穿和金叉编译为基于 `LAG()` 的每日事件行，再交给统一 `count_exp` 逻辑统计。
- 修正穿越事件窗口语义：`LAG()` 源数据保留目标窗口开始日前的历史行，事件次数只在 `event_rows.bizdate` 目标窗口内统计，避免漏判窗口首日上穿/下穿/金叉。
- 支持官方三表可解释的表达式级聚合 `count_exp`，例如 `indicator(..., AVG, CONS=每日) / indicator(... 每手股数 ...) < 阈值` 会编译为每日 bucket 行后再统计每日表达式是否满足。
- 补充 `涨停价`、`跌停价` 官方指标别名，分别映射到 `upSealPx`、`downSealPx` 并沿用价格单位换算。
- 补强官方口语日期归一化，覆盖 `过去20天`、`30个交易日`、`三个月之内`、`近半年`、`近5个月至今`、`2024年8月`、`9号`、`九月十五号`、`本季度` 等表达。
- `count_exp` 表达式比较支持同义日期 scope：当两个日期槽能无 warning 归一到同一日期窗口时，可以在同一个计数比较中使用。
- 官方 workbook 覆盖刷新为 `5,792/5,799` 可解析、`1,873` 条可落地编译，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 降至 `14`。

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
