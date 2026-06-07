# CHANGELOG

本文档记录 FinDSL Forge 的重要变更。详细提交历史以 Git 为准，提交包证据以 `submission_artifacts/evidence_snapshots/` 为准。

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
