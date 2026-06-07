# FinDSL Forge 项目文件索引

本文档是 FinDSL Forge 仓库的中文文件索引和归档说明。它面向项目维护者、比赛答辩成员、代码审查人员和后续接手开发者，用来快速判断每个目录“为什么存在、里面放什么、哪些文件是运行入口、哪些文件是证据产物、哪些文件不建议删除”。本文档根据当前代码、配置、测试、文档和提交证据推断整理，不删除任何文件；无法完全确认用途的内容会标注为“待确认”。

## 1. 项目总体说明

FinDSL Forge 是面向中国研究生金融科技创新大赛赛题 19 的金融选股 DSL 编译系统。项目核心目标是把受控的金融选股 DSL 编译为 Apache Doris SQL，并围绕正确性验证、长窗口加速、Doris 部署证据、自然语言到 DSL 辅助、Web Demo 和提交包证据形成完整工程交付。

项目主链路为：

```text
中文需求 / DSL / LLM 候选
  -> Lexer 词法分析
  -> Parser 语法分析
  -> AST 抽象语法树
  -> Semantic 语义校验
  -> SQL Generator 生成 Doris SQL
  -> Doris SQL Validator
  -> SQLite/Pandas 本地等价验证
  -> Doris 集群证据与提交包
```

更详细的项目介绍见 [docs/01_项目简介.md](docs/01_项目简介.md)，运行和部署见 [docs/03_操作手册.md](docs/03_操作手册.md) 与 [docs/12_环境依赖与部署.md](docs/12_环境依赖与部署.md)。

## 2. 根目录文件说明

| 文件/目录 | 类型 | 作用 | 是否建议保留 |
|---|---|---|---|
| `README.md` | 项目入口文档 | 说明项目目标、快速启动、核心能力、Doris 证据和提交流程。 | 必须保留 |
| `PROJECT_INDEX.md` | 文件索引 | 当前文件，统一说明目录、文件、归档建议和运行入口。 | 必须保留 |
| `CHANGELOG.md` | 更新日志 | 汇总版本变更、语义修复、证据刷新和维护记录。 | 必须保留 |
| `pyproject.toml` | Python 项目配置 | 声明包名、Python 版本、可选依赖、pytest 配置。 | 必须保留 |
| `.gitignore` | Git 忽略规则 | 忽略缓存、虚拟环境、生成数据、报告目录、日志等。 | 必须保留 |
| `.git/` | Git 元数据 | 本地版本控制目录，不应手工编辑。 | 必须保留 |
| `.pytest_cache/` | 测试缓存 | pytest 运行缓存，可清理，已被 `.gitignore` 忽略。 | 可清理 |
| `demo_8765*.log` 等 | 空日志文件 | Web Demo 端口启动时留下的日志占位，当前长度为 0。 | 可清理，删除前确认无运行进程依赖 |

## 3. 各文件夹作用说明

### `src/`

主程序源码目录。当前主要包为 `src/findsl/`，包含 DSL 编译器、SQL 生成、语义校验、Doris 资产生成、Web Demo、LLM 候选验证、readiness 门禁等模块。此目录只应放可发布、可测试的 Python 源码，不应放运行日志、临时截图或大数据文件。

### `configs/`

配置目录。当前包含 `functions.json`、`indicators.json`、`tables.json`。它们定义 DSL 函数签名、金融指标元数据、逻辑表到 Doris 物理表的映射。新指标优先在这里扩展，除非新增语义确实需要修改编译器。

### `data/`

数据目录，分为 `samples/`、`real_samples/` 和被忽略的 `generated/`。`samples/` 是轻量回归样本和官方风格用例，必须保留；`real_samples/` 是公开东方财富样本，用于展示真实 A 股代码和日期；`generated/` 是可再生成的规模数据，已被 `.gitignore` 忽略，不建议提交。

### `deploy/`

部署资产目录。`deploy/doris/` 保存 Doris schema、样例数据、prefix 表构建 SQL、smoke query 和 Docker Compose 快速启动文件。该目录是 Doris 环境复现和答辩证据的重要入口。

### `docs/`

项目文档目录。既包含已有的架构、Doris runbook、中文综合操作指南，也包含本次补齐的编号中文文档体系。今后新增说明文档应优先放在这里，除非属于提交包快照或报告产物。

### `scripts/`

辅助脚本目录。主要用于运行测试、生成报告、生成 Doris 资产、启动 Web Demo、采集 Doris 证据、导出提交包、生成中文手册和答辩视频。脚本应保持幂等或有清晰输出路径。

### `tests/`

测试目录。覆盖词法、语法、语义、SQL 生成、等价验证、Doris 资产、LLM 安全链路、Web Demo、readiness 和提交包。新增核心能力必须同步补测试。

### `reports/`

运行报告和 QA 产物目录。该目录已在 `.gitignore` 中忽略，包含 readiness 报告、Doris 证据、文档渲染 QA、UI 截图浏览器缓存等。它是本地工作产物，不是最终提交入口；最终轻量证据应通过 `scripts/export_submission_artifacts.ps1` 复制到 `submission_artifacts/evidence_snapshots/`。

### `submission_artifacts/`

提交包目录。包含技术报告、得分点映射、答辩脚本、Demo 截图、视频、证据快照和 evidence manifest。该目录中的内容面向比赛提交和离线审阅，应保持轻量、稳定、可读。

### `archive/`

历史归档目录。本次仅建立说明文件，不移动现有文件。后续如要归档旧报告、旧截图、旧视频或备份文件，应先在 [docs/16_历史文件说明.md](docs/16_历史文件说明.md) 记录来源和原因。

## 4. 核心代码文件说明

| 文件 | 主要功能 | 输入 | 输出/副作用 | 注意事项 |
|---|---|---|---|---|
| `src/findsl/lexer.py` | DSL 词法分析。 | DSL 字符串。 | Token 列表。 | 解析失败抛 `LexError`。 |
| `src/findsl/parser.py` | 递归下降语法分析。 | Token 或 DSL 字符串。 | AST 节点。 | 支持函数调用、命名参数、比较和布尔/算术表达式。 |
| `src/findsl/ast_nodes.py` | AST 数据结构。 | 解析阶段构造。 | 可序列化 AST。 | 供 compiler、semantic、sqlgen 共享。 |
| `src/findsl/semantic.py` | 语义校验。 | AST、Registry。 | 类型判断或异常。 | 拦截未知指标、窗口错误、裸字段、非法 rank 参数等。 |
| `src/findsl/sqlgen.py` | Doris SQL 生成与优化。 | 已校验 AST。 | SQL、trace、explain。 | 负责窗口物化、rank、date pushdown、prefix-sum rewrite。 |
| `src/findsl/compiler.py` | 编译器总入口。 | DSL 字符串。 | `CompileResult`。 | 串联 parse、semantic、SQL 生成和 Doris SQL validation。 |
| `src/findsl/doris_sql.py` | 生成 SQL 安全形态验证。 | SQL 字符串。 | Validation result。 | 阻止多语句、DDL/DML、未知表和 window-in-WHERE。 |
| `src/findsl/reference.py` | Pandas reference oracle。 | DSL 与 CSV 数据。 | 参考结果行。 | 用于独立语义校验，需保持与 SQL 三值逻辑一致。 |
| `src/findsl/executor.py` | SQLite 本地执行器。 | 生成 SQL、CSV 样本。 | SQL 结果行。 | 注册 Doris 兼容函数，如 `CEIL`，用于本地等价验证。 |
| `src/findsl/equivalence.py` | SQL/reference 等价比较。 | DSL、数据目录。 | missing/extra keys。 | 对比赛正确性证据非常关键。 |
| `src/findsl/registry.py` | 配置加载。 | `configs/*.json`。 | Registry 对象。 | 新指标、新表、新函数优先走配置。 |
| `src/findsl/nl2dsl.py` | 中文自然语言模板到 DSL 候选。 | 中文文本。 | 候选 DSL 列表。 | 不是自由生成 SQL，只生成受控 DSL。 |
| `src/findsl/llm_adapter.py` | LLM 输出提取与安全验证。 | LLM 文本/JSON。 | accepted/rejected candidates。 | 直接 SQL 和无效 DSL 会被拒绝。 |
| `src/findsl/llm_provider.py` | OpenAI-compatible provider 调用。 | API 配置、中文文本。 | LLM 候选验证结果。 | Provider 输出仍需走 compiler 和 oracle。 |
| `src/findsl/demo.py` | Web Demo 和 JSON API。 | HTTP 请求。 | HTML/API 响应。 | 默认运行在 `127.0.0.1:8765`。 |
| `src/findsl/doris.py` | Doris DDL/SQL 资产生成。 | 配置与样本数据。 | `deploy/doris/*.sql`。 | 与 registry 强绑定，保证表和指标一致。 |
| `src/findsl/doris_evidence.py` | Doris 集群证据采集。 | MySQL 客户端配置、DSL。 | Markdown/JSON evidence。 | 需真实 Doris 9030 端口和已加载数据。 |
| `src/findsl/readiness.py` | 提交前综合门禁。 | 项目目录、报告目录。 | readiness report。 | 评估测试、证据、官方套件和 Git clean 状态。 |
| `src/findsl/defense_package.py` | 答辩证据包生成。 | 样本、报告、配置。 | defense package。 | 映射演示步骤到得分点。 |
| `src/findsl/official_suite.py` | 官方风格用例套件。 | JSONL 正/负例。 | coverage report。 | 正例和负例均为 required gate。 |
| `src/findsl/benchmark.py` | prefix-sum 本地基准。 | DSL、样本数据。 | benchmark report。 | 本地 SQLite timing 只作回归信号。 |
| `src/findsl/scale_benchmark.py` | 长窗口规模基准编排。 | 合成数据参数。 | scale benchmark report。 | 不替代 Doris 集群性能证据。 |
| `src/findsl/synthetic.py` | 合成市场数据生成。 | 股票数、日期数、随机种子。 | CSV 数据。 | 生成数据默认放 `data/generated/`。 |
| `src/findsl/diagnostics.py` | 诊断和修复建议。 | 异常对象。 | 结构化诊断。 | Web Demo 和 CLI 共享。 |
| `src/findsl/cli.py` | 命令行入口。 | `python -m findsl.cli ...`。 | 各类命令输出。 | 所有常用流程均从这里暴露。 |

## 5. 配置文件说明

| 文件 | 作用 | 维护建议 |
|---|---|---|
| `configs/functions.json` | 定义 DSL 函数参数个数、命名参数和返回类型。 | 新增函数时先明确输入输出语义，再同步 semantic/sqlgen/reference/tests。 |
| `configs/indicators.json` | 定义指标类型、来源表、列名、是否支持 prefix-sum。 | 新增普通数值指标通常只需配置；支持 prefix-sum 时必须补 prefix table 信息。 |
| `configs/tables.json` | 定义逻辑表、物理表、别名、日期列、证券代码列、分区列。 | 修改物理表名后必须重新生成 Doris 资产和报告。 |
| `pyproject.toml` | Python 包和测试配置。 | 当前核心运行无强依赖；`dev`/`eval` 依赖用于 pandas/pytest。 |
| `.gitignore` | 忽略生成数据、报告、日志、缓存。 | 不建议提交 `reports/`、`data/generated/`、`.pytest_cache/`。 |

## 6. 数据文件说明

| 路径 | 内容 | 用途 | 是否提交 |
|---|---|---|---|
| `data/samples/daily_quote.csv` | 小型行情样本。 | 单元测试、CLI 示例、Web Demo 默认数据。 | 是 |
| `data/samples/money_flow.csv` | 小型资金流样本。 | 多表 join、稀疏辅助表、prefix-sum 语义测试。 | 是 |
| `data/samples/stock_universe.csv` | 市场归属样本。 | `market("A")`、`market("B")` 过滤。 | 是 |
| `data/samples/queries.jsonl` | 编译评估用例。 | `evaluate` 和 readiness。 | 是 |
| `data/samples/official_positive_cases.jsonl` | 官方风格正例。 | official-suite。 | 是 |
| `data/samples/official_negative_cases.jsonl` | 官方风格负例。 | diagnostics 和安全边界。 | 是 |
| `data/samples/llm_candidate_response.json` | 模拟 LLM 输出。 | 验证 LLM 安全适配器。 | 是 |
| `data/real_samples/eastmoney_a_share_sample/` | 东方财富公开行情小样本。 | 真实 A 股代码、日期和字段展示。 | 是 |
| `data/real_samples/.../raw/*.json` | 原始接口响应缓存。 | 样本来源可追溯。 | 是 |
| `data/generated/` | 合成规模数据。 | Doris/SQLite 规模实验。 | 否，已忽略 |

## 7. 文档文件说明

### 已有主要文档

| 文件 | 作用 | 当前建议 |
|---|---|---|
| `docs/architecture.md` | 英文架构说明，覆盖编译器、验证、Doris 证据链。 | 保留，作为架构原始文档。 |
| `docs/doris_runbook.md` | Doris 部署和证据采集 runbook。 | 保留，编号文档中引用。 |
| `docs/development_plan.md` | 分阶段开发计划。 | 保留，历史规划与路线依据。 |
| `docs/defense_walkthrough.md` | 答辩流程。 | 保留。 |
| `docs/requirement_mapping.md` | 赛题要求映射。 | 保留。 |
| `docs/submission_package.md` | 提交包生成说明。 | 保留。 |
| `docs/ui_redesign_plan.md` | Web Demo UI 改造规划。 | 保留，属于历史设计决策。 |
| `docs/FinDSL_Forge_中文综合操作指南.md/.docx` | 长篇中文综合文档。 | 保留，作为正式说明书。 |
| `docs/FinDSL_Forge_中文操作手册.md/.docx/.pdf` | 中文操作手册。 | 保留，作为用户/操作手册。 |

### 本次补齐文档

本次新增 `docs/01_项目简介.md` 到 `docs/17_项目交付说明.md`，作为统一中文文档体系。编号文档不会覆盖旧文档，而是提供清晰入口、补充中文解释，并引用已有详细资料。

## 8. 历史文件说明

历史或可归档内容包括：

| 路径 | 原因 | 建议 |
|---|---|---|
| `reports/doris_cluster_evidence_*_threshold_probe.md` | 阈值探测报告，不是最终默认证据。 | 可归档到 `archive/reports/`，暂不删除。 |
| `reports/manual_*` | Word/PDF 渲染 QA 产物。 | 可归档或保留在本地，不建议提交。 |
| `reports/_docx_qa_deps/` | 文档 QA 依赖缓存，体积较大。 | 可清理或转移到本地工具缓存。 |
| `reports/ui_redesign_qa/*profile*` | 浏览器自动化缓存。 | 可清理。 |
| 根目录 `demo_8765*.log` 等 | 空日志文件，已被 `.gitignore` 忽略。 | 可清理，确认没有运行中的 Demo 后删除。 |
| `data/generated/` | 可再生成的合成规模数据。 | 不提交；需要复现实验时重新生成。 |

详细记录见 [docs/16_历史文件说明.md](docs/16_历史文件说明.md)。

## 9. 最新版本文件说明

当前最新源码以 `src/findsl/`、`configs/`、`tests/`、`scripts/`、`deploy/doris/`、`submission_artifacts/evidence_snapshots/` 为准。最终提交证据以 `submission_artifacts/evidence_manifest.md` 和 `submission_artifacts/evidence_snapshots/submission_readiness.md` 为准，不以被忽略的 `reports/` 为最终交付依据。

## 10. 不建议删除的文件

不建议删除：

- `src/findsl/*.py`
- `configs/*.json`
- `data/samples/*`
- `data/real_samples/eastmoney_a_share_sample/*`
- `deploy/doris/*`
- `scripts/*.ps1` 与核心 Python 脚本
- `tests/*.py`
- `README.md`
- `PROJECT_INDEX.md`
- `CHANGELOG.md`
- `docs/*.md`
- `submission_artifacts/*`

这些文件构成项目运行、测试、部署、答辩和回溯链路。

## 11. 可归档/可清理/疑似无用文件

| 类型 | 路径 | 判断 | 建议 |
|---|---|---|---|
| pytest 缓存 | `.pytest_cache/` | 自动生成，可再生。 | 可清理。 |
| 空日志 | `demo_876*.log` | 当前为 0 字节。 | 可清理，删除前确认服务未运行。 |
| 报告缓存 | `reports/_docx_qa_deps/` | 文档 QA 依赖缓存，非源码。 | 可清理或归档。 |
| 浏览器缓存 | `reports/ui_redesign_qa/*profile*` | Playwright/Chrome profile 缓存。 | 可清理。 |
| 合成数据 | `data/generated/` | 可由脚本重新生成。 | 不提交，可按需保留本地。 |
| 阈值探测报告 | `reports/doris_cluster_evidence_*threshold_probe.md` | 辅助实验，不是最终证据。 | 可归档到 `archive/`。 |

## 12. 项目运行入口

### CLI 入口

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") > 10)'
python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples
python -m findsl.cli official-suite --json
python -m findsl.cli readiness-report --output reports/submission_readiness.md
```

### Web Demo 入口

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1
```

默认访问 `http://127.0.0.1:8765`。

### Doris 资产入口

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

### 提交证据入口

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

## 13. 项目构建、运行、测试流程

推荐顺序：

1. 设置 Python 路径：`$env:PYTHONPATH="src"`。
2. 运行全量测试：`python -m pytest -q`。
3. 运行官方风格套件：`python -m findsl.cli official-suite --json`。
4. 运行 readiness：`powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1`。
5. 如果需要 Doris 证据，先按 [docs/12_环境依赖与部署.md](docs/12_环境依赖与部署.md) 启动 Doris，再采集证据。
6. 最终提交前执行 `scripts/export_submission_artifacts.ps1`。

## 14. 后续维护建议

1. 新增 DSL 函数时，必须同时更新 `configs/functions.json`、`semantic.py`、`sqlgen.py`、`reference.py`、测试和文档。
2. 新增指标时优先走 `configs/indicators.json`；如支持 prefix-sum，需要同步 Doris schema 和 prefix 构建逻辑。
3. 修改 SQL 生成后必须跑 `tests/test_equivalence.py`，防止 SQL 与 reference oracle 分歧。
4. 修改 Doris 表结构后必须重新生成 `deploy/doris/*.sql`，并重新采集或标注 Doris 证据。
5. `reports/` 只作为本地输出目录；最终可提交证据通过 `submission_artifacts/` 管理。
6. 历史文件不要直接删除，先记录在 [docs/16_历史文件说明.md](docs/16_历史文件说明.md)，必要时移动到 `archive/`。

