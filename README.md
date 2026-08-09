# FinDSL Forge

FinDSL Forge 是第五届中国研究生金融科技创新大赛赛题 19“行情选股 DSL 到高性能 Doris SQL 的自动化编译系统”的工程实现。系统把官方七槽位选股 DSL 编译为经过类型检查、安全校验和物理优化的 Apache Doris SQL，并为正确性、性能、数据来源和比赛交付建立可复现证据。

当前开发以 [docs/00_当前开发主线.md](docs/00_当前开发主线.md) 为唯一路线，以 [PROJECT_INDEX.md](PROJECT_INDEX.md) 为文件索引。阶段报告和旧方案已归档到 [docs/history/](docs/history/README.md)，不再与当前实现混用。

## 当前结论

项目已经形成 ANTLR4 前端、强类型 AST、领域绑定、Logical IR、规则优化、Physical IR、SQLGlot Doris 后端和真实 Doris 验证链。P0/P1 集中补强已完成正式正确率扩容、复合布尔作用域修复、异常账本、日期通用规则、复权策略基准、Doris 持久化与水位门禁、幂等装载和性能口径治理。架构方向与赛题要求一致，不需要推倒重来；后续重点是把正式真值集继续扩到内部 240 条目标、完成真正新函数的零核心代码盲扩展，并在功能冻结后统一制作最终材料。

不得把以下指标混为一个“正确率”：

| 指标 | 当前证据值 | 正确解释 |
| --- | ---: | --- |
| 严格解析 | `5792/5799` | 原始官方 DSL 不经修复的语法通过数。 |
| 恢复解析 | `5799/5799` | 7 条已知格式缺陷经过可审计恢复后均可解析。 |
| 旧成功集迁移 | `1044/1097`，`95.17%` | 新后端覆盖旧后端已确认能力的比例，不是 SQL 正确率。 |
| 新后端总成功 | `1083/5799` | 正式新链路当前生成受控 SQL 的行数；其余包含数据缺失、非法输入和能力缺口。 |
| 正式 SQL 正确率 | `157/157`，Wilson 95% 下界 `97.61%` | 独立 reference SQL 与生成 SQL 的完整结果集一致；12 类函数每类至少 10 条。 |
| 官方正负例 | `37/37 + 37/37` | 固定正例编译通过、固定负例按预期拒绝。 |
| 长周期性能门禁 | 官方真实数据本轮 `14.381x` | 同一长周期 DSL 的 baseline/optimized 完整结果哈希一致，达到赛题 `>=10x`。 |
| 其他性能证据 | `12.182x` / `24.510x` / `1.393x` / `1.173x` | 分别属于常规官方窗口、500 万行合成扩展、Phase 6C 投影和早期六查询矩阵，不得写成系统平均值。 |
| 编译延迟 | P95 `1.257ms` | 当前冻结基准远低于赛题 `<50ms` 门槛。 |

正式提交前必须在当前 HEAD 和同一数据快照上重新采集证据。现有历史性能数字不能替代最终封板结果。

## 官方语料缺口

官方 5799 条语料已按根因重新分类，开发单位是“能力族”，不是 Excel 行号：

| 分类 | 行数 | 处理方式 |
| --- | ---: | --- |
| 已通过 | 1083 | 保持回归，不重复开发。 |
| 数据不可用错误码 | 1720 | 接入完整且版本化的数据目录，或返回结构化不可用诊断。 |
| 非法输入错误码 | 2466 | 严格模式稳定拒绝；恢复模式仅允许白名单修复。 |
| 能力缺口错误码 | 530 | 按约束、日期、时序和排名等通用能力族实现。 |

使用下列命令重建当前分类报告：

```powershell
$env:PYTHONPATH = "src"
python scripts/analyze_official_gaps.py reports/phase48_scope_semantic_policy_funnel.json `
  --json-output reports/current_official_gap_taxonomy.json `
  --markdown-output reports/current_official_gap_taxonomy.md
```

任何生产分支都不得匹配完整 DSL 文本、工作簿行号或单个证券名称。数据范围只有在来源、成员完整性、快照日期、许可和历史有效期可说明时，才进入正式目录；否则 fail closed，不生成伪 SQL。

## 架构

```text
官方 DSL
  -> OfficialSlot.g4 / ANTLR4
  -> Immutable Typed AST
  -> Semantic Policy Binder
  -> Domain Model
  -> Canonical Relational IR
  -> Equivalence Rewrite Rules
  -> Physical Candidate Planner + Cost/Risk Selector
  -> Validated Physical IR
  -> SQLGlot Doris AST / SQL
  -> Doris Execute / Explain / Profile
  -> Independent Oracle / Evidence Manifest
```

正式官方编译器位于 `src/findsl/official/`。手写官方前端和双前端差分已移到 `src/findsl/compat/official_frontend/`；旧 `lexer.py`、`parser.py`、`semantic.py`、`sqlgen.py`、`compiler.py` 和 `official_slot.py` 暂时保留为内部样例、兼容入口和迁移差分基线，不再承接新官方语义。依赖边界由 `import-linter` 强制：整个新官方包不能反向依赖旧管道。决策依据见 [ADR-0001](docs/adr/0001-官方编译器主线与兼容层边界.md)。

项目复用成熟组件的边界如下：

- ANTLR4 负责文法解析和错误位置，不手写第二套正式语法。
- SQLGlot 负责 Doris SQL AST 和方言渲染，不拼接任意 SQL 字符串。
- Apache Doris Nereids、统计、分区和物化视图负责数据库内优化。
- 项目自研部分聚焦金融 DSL 类型、业务语义、关系 IR、候选规划、成本风险和证据合同。

## 快速开始

建议使用 Python 3.11；项目最低支持 Python 3.9。

```powershell
python -m pip install -e ".[dev]"
python -m pytest
$env:PYTHONPATH = "src"
```

数据运行模式由 `FINDSL_DATA_PROFILE` 显式选择：

```powershell
# 评委复现与官方数据基线：不引用外部成员、行业、指数行情或交易规则表
$env:FINDSL_DATA_PROFILE = "official_only"

# 扩展能力验证：使用已经登记的公开数据快照；执行前必须装载相应外部表
$env:FINDSL_DATA_PROFILE = "enriched_public"
```

`official_only` 可以随赛题方数据包离线复现；`enriched_public` 的编译请求不会临时联网，但第三方成员数据受许可约束，干净环境必须按来源清单重新同步和装载，不能把本机缓存当成交付依赖。来源清单见 [external_source_registry.json](configs/official/external_source_registry.json)，当前缺口裁决见 [数据缺口逐条审计](submission_artifacts/evidence_snapshots/current_scope_data_gap_audit.md)。

解析、生成 IR 和 Doris SQL：

```powershell
python -m findsl.cli official-slot-parse `
  "indicator('', '', '涨幅', '今日', '', '', '') > 5%" `
  --mode strict --frontend antlr --json

python -m findsl.cli official-slot-ir `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" --json

python -m findsl.cli official-slot-backend `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" --json
```

启动演示：

```powershell
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
```

浏览器访问 `http://127.0.0.1:8765`。比赛演示使用“官方赛题编译链”入口；内部 FinDSL 入口只用于保留的样例和安全辅助说明。

## 质量门禁

```powershell
python scripts/generate_antlr.py --check
python -m ruff check .
lint-imports
python -m pytest
python -m findsl.cli official-suite --json
python -m findsl.cli readiness-report --output reports/submission_readiness.md
```

`lint-imports` 在 Windows 用户安装后若不在 PATH，可直接调用 `%APPDATA%\Python\Python39\Scripts\lint-imports.exe`，或重新打开终端。CI 使用已安装命令。

门禁分别证明不同事项：测试通过不等于真实 Doris 正确；迁移通过不等于独立真值正确；SQL 能执行不等于业务语义正确；空结果不能作为唯一正确性证据。正式正确性要比较完整有序结果、行数和 SHA-256，并由不复用被测规划器的独立 oracle 产生期望结果。

## Doris

部署资产位于 `deploy/doris/`，完整操作见 [docs/doris_runbook.md](docs/doris_runbook.md)。快速环境使用命名卷保存 FE 元数据与 BE 数据，健康检查同时覆盖 FE HTTP、BE HTTP、查询端口和 alive backend：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\doris_quickstart.ps1 -Action Start
python scripts\check_official_watermarks.py
```

正确率和性能脚本默认先执行水位门禁，要求基础、技术、前缀和汇总路径的行数、交易日数及起止日期一致。Stream Load 使用文件 SHA-256 派生标签、`strict_mode:true`、`max_filter_ratio:0` 和 `NumberFilteredRows=0` 门禁；数据已完整时复用现有表，不重复清表。

## 文档与证据

- [文档导航](docs/README.md)
- [当前开发主线](docs/00_当前开发主线.md)
- [赛题要求映射](docs/requirement_mapping.md)
- [严格口径说明](docs/36_严格官方编译基线与口径说明.md)
- [缺失数据域审计](docs/35_官方三表缺失数据域不可伪造SQL审计报告.md)
- [操作手册](docs/FinDSL_Forge_中文操作手册.md)
- [提交说明](docs/17_项目交付说明.md)
- [机器可读证据](submission_artifacts/evidence_metadata.json)
- [证据摘要](submission_artifacts/evidence_summary.md)
- [外部数据来源与快照清单](submission_artifacts/evidence_snapshots/current_external_data_inventory.md)
- [53条严格迁移缺口逐条审计](submission_artifacts/evidence_snapshots/current_scope_data_gap_audit.md)

`reports/` 是可再生成的本地工作产物；`submission_artifacts/evidence_snapshots/` 是提交用快照。导出前必须确认所有 current 证据使用同一 Git HEAD、配置指纹和数据快照，历史证据只能进入 historical 分组。

## 开发规则

1. 先确定失败属于语法、类型、语义、关系表达、物理规划、数据或非法输入，再改代码。
2. 一次实现一个通用能力族，并回归全部受影响语料；不按单句打补丁。
3. 新指标优先进入版本化目录；新函数通过受控签名、模板或插件扩展，不能执行任意配置 SQL。
4. 等价规则只产生语义等价候选，成本模型只负责选择；两者不得混写。
5. 新官方核心不得依赖旧管道，CI 发现依赖回退直接失败。
6. 文档只解释当前代码和证据，不得用旧数字覆盖事实。
7. 完成的含义是实现、测试、真实执行、版本一致证据和可复现说明全部闭环。

## 项目状态

当前是高完成度的竞赛工程原型和企业级内核基线，不应提前宣称评委“必然满分”或已达到生产正式发布。赛题正确率、12 类函数覆盖、官方长周期 `>=10x`、编译 P95、48 条 `<10s` 矩阵和本地 Doris 可复现性已有强证据；剩余高价值工作是把正式正确率集扩到内部 240 条、完成真正新函数/窗口模板的零核心代码盲扩展、在最终提交 HEAD 重采并封装证据。API 安全、完整可观测性和多节点高可用属于产品化增强，不作为本轮竞赛 P0/P1 阻塞。具体顺序和停止条件以 [当前开发主线](docs/00_当前开发主线.md) 为准。
