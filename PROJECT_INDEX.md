# FinDSL Forge 项目文件索引

本文按当前代码事实说明仓库结构、正式入口、兼容边界、文档状态和可清理内容。开发路线见 [docs/00_当前开发主线.md](docs/00_当前开发主线.md)，文档选择见 [docs/README.md](docs/README.md)。无法仅凭代码确认的业务语义继续标为待核验，不以推测替代官方定义。

## 1. 项目总体说明

FinDSL Forge 将赛题 19 的官方七槽位行情选股 DSL 编译为 Apache Doris SQL。正式链路为 ANTLR4 → Typed AST → 语义绑定 → Domain Model → Logical IR → 规则优化 → Physical IR → SQLGlot Doris SQL → 执行与独立结果核验。

仓库仍保留早期内部 FinDSL 编译器和官方兼容入口，它们用于样例、迁移差分和回归，不是后续新增官方能力的开发位置。正式边界见 [ADR-0001](docs/adr/0001-官方编译器主线与兼容层边界.md)。

## 2. 根目录文件

| 路径 | 作用 | 维护规则 |
| --- | --- | --- |
| `README.md` | 项目入口、当前事实、快速运行和开发规则。 | 必须与当前代码一致，禁止堆叠阶段日志。 |
| `PROJECT_INDEX.md` | 当前文件；解释目录、文件和状态。 | 目录职责变化时更新。 |
| `CHANGELOG.md` | 版本变更记录。 | 记录用户可见和架构级变化，不代替主路线。 |
| `pyproject.toml` | Python 版本、依赖、测试、Ruff 和 import-linter 配置。 | 必须保留并接受 CI 校验。 |
| `.github/workflows/test.yml` | ANTLR、静态检查、依赖边界和测试流水线。 | 正式质量门禁，不应绕过。 |
| `.gitignore` | 缓存、生成数据和本地产物忽略规则。 | 新增生成目录时同步维护。 |
| `LICENSE` | 许可文件。 | 待提交前复核依赖许可和原创性声明。 |

## 3. 目录职责

| 目录 | 为什么存在 | 应放内容 | 不应放内容 |
| --- | --- | --- | --- |
| `src/findsl/` | 可安装的 Python 产品代码。 | 编译核心、服务、证据与工具模块。 | 报告、截图、大数据、临时脚本。 |
| `src/findsl/official/` | 官方 DSL 唯一正式编译器。 | 前端、类型、语义、领域模型、IR、优化、物理规划、Doris 后端。 | 对旧编译管道的反向依赖、按语句硬编码。 |
| `configs/` | 版本化声明与策略。 | 指标、函数、表、物理策略、语义政策和 Schema。 | 任意可执行 SQL、密钥、临时参数。 |
| `data/` | 输入样例和可复现实验数据。 | 小型样例、公开样例、官方数据引用说明、生成数据目录。 | 无来源的第三方数据、提交不允许的大文件。 |
| `deploy/doris/` | Doris 建库、表、导入和 smoke 资产。 | 幂等 SQL、Compose、导入与健康检查材料。 | 本机密码、不可复现手工状态。 |
| `docs/` | 当前有效说明和比赛材料。 | 唯一主路线、正式规范、手册、验收、答辩。 | 每轮临时复盘和重复计划。 |
| `docs/history/` | 已替代与阶段材料的可追溯归档。 | 旧计划、阶段报告、历史实施记录。 | 当前唯一规范。 |
| `docs/adr/` | 长期架构决策。 | 决策背景、选择、理由、影响和退出条件。 | 日常进度、待办清单。 |
| `scripts/` | 可复现辅助入口。 | 证据采集、数据同步、构建、检查和发布脚本。 | 一次性且无说明的实验片段。 |
| `tests/` | 自动化验证。 | 单元、属性、集成、Doris、证据和 UI 测试。 | 生产代码或真实密钥。 |
| `reports/` | 本地可再生成报告。 | 当前运行输出、分析和临时 QA。 | 唯一不可重建的提交证据。 |
| `submission_artifacts/` | 面向评委的轻量交付证据。 | 当前快照、metadata、摘要、报告和截图。 | 未标版本的历史数字。 |
| `archive/` | 非文档类旧资产归档。 | 经记录的旧产物和保留文件。 | 当前运行依赖。 |

## 4. 正式核心代码

### 4.1 官方编译入口

| 文件/目录 | 主要功能 | 输入 | 输出 | 关系与注意事项 |
| --- | --- | --- | --- | --- |
| `src/findsl/official/pipeline.py` | 正式编译编排。 | 官方 DSL、模式、目录与策略。 | 各阶段结果、SQL 或结构化诊断。 | 只协调阶段，不应承载具体语义。 |
| `src/findsl/official/frontend/` | ANTLR 前端、协议和适配。 | DSL 文本。 | 统一 AST 与源位置信息。 | `OfficialSlot.g4` 是正式语法源；generated 由脚本生成。 |
| `src/findsl/official/typed_ast.py` | 不可变强类型语法树。 | 前端 AST 与绑定信息。 | 有类型、可审计节点。 | 进入 IR 前消除未知类型。 |
| `src/findsl/official/semantics.py` | 函数签名、参数、类型和槽位约束。 | AST、Registry。 | Typed AST 或稳定错误码。 | 不选择物理表，不调用旧语义模块。 |
| `src/findsl/official/domain/` | 金融业务概念绑定。 | Typed AST、语义政策、范围目录。 | 领域表达和数据需求。 | 未定义/缺数据时 fail closed。 |
| `src/findsl/official/ir/` | SQL 无关的关系 IR。 | 已绑定领域模型。 | Filter、Project、Join、Aggregate、Window、Rank 等关系节点。 | 不含 Doris 表名或 SQL 字符串。 |
| `src/findsl/official/optimizer/` | 等价重写规则与解释轨迹。 | Logical IR。 | 等价候选和规则 trace。 | 规则负责等价，不负责成本选择。 |
| `src/findsl/official/physical/` | 物理目录、候选规划、统计和 Physical IR。 | Logical IR、Catalog Snapshot、Statistics。 | 可验证物理候选与选择依据。 | `planner.py` 仍偏大，是后续拆分重点。 |
| `src/findsl/official/backend/` | SQLGlot Doris AST、渲染、安全校验和执行。 | Physical IR。 | 单条只读 Doris SQL、执行/差分结果。 | 禁止把任意配置字符串直接拼入 SQL。 |
| `src/findsl/official/external/` | 外部范围与成员数据 Provider。 | 版本、日期、来源配置。 | 带来源和有效期的目录快照。 | 模糊别名不得自动进入正式目录。 |
| `src/findsl/official/errors.py` | 官方核心错误基类。 | 阶段失败信息。 | 稳定异常与错误码载体。 | 兼容层可引用，核心不反向引用兼容层。 |
| `src/findsl/official/literals.py` | 范围、百分比等共享字面量解析。 | 字符串。 | 规范化值。 | 消除 `official_slot.py` 中重复实现。 |

### 4.2 证据与评估

| 文件 | 作用 | 关键输出 |
| --- | --- | --- |
| `src/findsl/official_gap_analysis.py` | 把 5799 条结果按能力族归类。 | passed/data_unavailable/invalid_input/capability_gap 统计。 |
| `src/findsl/official_coverage_funnel.py` | 生成各阶段漏斗与终止错误。 | JSON/Markdown 漏斗。 |
| `src/findsl/official_*_evidence.py` | 采集前端、IR、领域、后端、前缀等专项证据。 | 版本化报告。 |
| `src/findsl/evidence_metadata.py` | 聚合提交快照的机器可读索引。 | `evidence_metadata.json` 与摘要。 |
| `src/findsl/readiness.py` | 提交前综合门禁。 | readiness 报告和阻断项。 |
| `src/findsl/official_suite.py` | 固定官方风格正负例。 | 覆盖和诊断结果。 |
| `src/findsl/equivalence.py` / `reference.py` | 独立 SQL/reference 等价验证。 | 缺失、额外、顺序和结果差异。 |

### 4.3 兼容和非正式入口

`src/findsl/compat/official_frontend/` 保存迁移期手写前端和 ANTLR/手写差分；`src/findsl/official_slot.py`、`compiler.py`、`lexer.py`、`parser.py`、`semantic.py` 和 `sqlgen.py` 属于早期管道。它们仍可能被内部样例、历史 CLI 或迁移测试调用，因此暂不删除；后续只允许缩小为 facade 或只读基线。新增官方函数、语义和物理策略不得写入这些文件。

`src/findsl/demo.py` 是演示服务，必须调用应用服务/正式 pipeline，不得复制编译规则。`nl2dsl.py`、`llm_adapter.py` 和 `llm_provider.py` 只生成或筛选 DSL 候选，模型输出不能绕过确定性编译器和安全校验。

## 5. 配置文件

| 路径 | 作用 | 当前注意事项 |
| --- | --- | --- |
| `configs/indicators.json` | 指标名、类型、来源列和物理能力。 | 新指标优先配置扩展，但必须验证列和数据域真实存在。 |
| `configs/functions.json` | 早期内部函数目录。 | 不等同于正式官方函数零代码扩展能力。 |
| `configs/tables.json` | 逻辑表到物理表映射。 | 与 Doris schema 和数据快照一致。 |
| `configs/official/` | 官方指标、资源、物理策略、范围和政策。 | 后续统一 Catalog Snapshot 与 schema 校验。 |

任何配置发布都应产生版本、内容哈希和 catalog fingerprint。密钥只通过环境变量或秘密管理注入。

## 6. 数据文件

- `data/samples/`：快速单元和参考执行数据，必须小、确定、可提交。
- `data/real_samples/`：带来源说明的公开样例，只证明所含数据域。
- `data/generated/`：可再生成规模数据，默认不提交。
- 官方赛题数据：必须记录原文件 SHA-256、接收日期、表结构和使用限制，不得根据缺失列伪造事实。
- 外部成员数据：必须带 Provider、原始响应、快照时间、有效期、成员数和人工审核状态。

## 7. 文档状态

当前有效文档列在 [docs/README.md](docs/README.md)。`docs/history/phase_reports/`、`legacy_plans/` 和 `implementation_records/` 已归档，不再作为当前开发依据。长篇 Word/PDF 手册是发布材料，证据刷新后需重新生成并做版面检查。

## 8. 当前版本与历史

当前正式代码在分支 `feat/antlr-calcite-architecture`。Git HEAD 是代码身份，证据还必须同时记录配置指纹、数据快照和 Doris 版本。仓库里存在多个历史 HEAD 的真实证据；它们可以用于趋势比较，但最终结论必须用同一当前 HEAD 重新生成。

阶段演进不再写入根 README。需要追溯时查看 `CHANGELOG.md`、`docs/history/` 和 Git log。

## 9. 不建议删除

- `src/findsl/official/`、`configs/official/`、正式 grammar 与 generated ANTLR 文件；
- `tests/` 中当前门禁测试；
- `deploy/doris/` 和 Doris runbook；
- `data/samples/` 与已声明来源的真实样例；
- `submission_artifacts/evidence_snapshots/` 中进入 manifest 的证据；
- `docs/00_当前开发主线.md`、ADR、赛题规范、操作和交付文档；
- 旧管道文件，直到兼容调用图和迁移退出门禁完成。

## 10. 可归档或可清理

| 内容 | 处理建议 | 原因 |
| --- | --- | --- |
| `__pycache__/`、`.pytest_cache/` | 可直接重建，保持忽略。 | Python/pytest 缓存。 |
| 空的 Demo 日志和浏览器 profile | 服务停止后清理。 | 不含产品事实。 |
| `reports/` 中旧 HEAD 报告 | 迁入历史证据区或重新生成。 | 不能证明当前版本。 |
| 重复截图、临时渲染页 | 先核对 manifest，再归档。 | 避免提交包膨胀。 |
| 阶段计划与阶段复盘 | 已迁入 `docs/history/`。 | 被唯一主线替代。 |
| 大型 planner/backend 中已废弃私有函数 | 先做调用图和测试，再删除。 | 不能靠文件名判断无用。 |

本轮没有删除受 Git 管理的历史文件。代码清理必须先证明符号无调用、门禁通过且兼容边界不受影响。

## 11. 运行入口

```powershell
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
python -m findsl.cli official-slot-backend "indicator('', '', '成交量', '今日', '', '', '') > 100" --json
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
```

数据和 Doris 运行按 [docs/doris_runbook.md](docs/doris_runbook.md) 操作。所有 CLI 参数以 `python -m findsl.cli --help` 和子命令 `--help` 为准。

## 12. 构建、测试与提交

推荐顺序：

```powershell
python scripts/generate_antlr.py --check
python -m ruff check .
lint-imports
python -m pytest
python -m findsl.cli official-suite --json
python -m findsl.cli readiness-report --output reports/submission_readiness.md
```

真实 Doris 可用后再执行健康、数据行数、统计、正确性、性能矩阵与证据导出。提交前检查 Git 状态、当前 HEAD、metadata、Markdown、截图和手册口径一致，然后生成 SHA-256 manifest。

## 13. 后续维护

1. 以能力族而非单条语料安排任务。
2. 保持新官方核心到旧管道的依赖禁令。
3. 用 `CompileContext/CatalogSnapshot` 固定一次编译所见的配置和数据版本。
4. 继续拆分超大 planner、backend 和 validator，但每次拆分保持行为与证据不变。
5. 将正式 SQL 正确率、迁移率、解析率和编译成功率分别统计。
6. 只有完整、版本化、可审计的数据 Provider 能补齐范围；不做未经证实的模糊映射。
7. 每个阶段完成后把稳定结论合并到正式文档，阶段记录转入历史区。
8. 每次发布都从干净环境重建、执行门禁、刷新当前证据并做人工答辩演练。
