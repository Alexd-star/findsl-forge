# FinDSL Forge

[![test](https://github.com/Alexd-star/findsl-forge/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/Alexd-star/findsl-forge/actions/workflows/test.yml)

FinDSL Forge 是第五届中国研究生金融科技创新大赛赛题 19“行情选股 DSL 到高性能 Doris SQL 的自动化编译系统”的工程实现。系统接收官方七槽位选股 DSL，经过语法解析、类型与业务语义检查、关系计划优化和物理计划选择，输出经过结构校验的 Apache Doris SQL；同时保留正确性、性能、数据来源和版本身份的可复核证据。

## 当前状态

项目已经完成正式编译器主链路和赛题硬指标开发，定位是“可复现的高完成度竞赛工程”，不是已经上线的证券生产系统，也不承诺评委主观评分。所有数字均按独立正确率、迁移覆盖率、全量语料覆盖率和性能工作负载分别统计，不能互相替代。

| 赛题指标 | 当前证据 | 结论 |
| --- | --- | --- |
| ANTLR4/BNF 与复合逻辑 | strict `5792/5799`；7 条可审计恢复后 `5799/5799` | 已实现；严格与恢复口径分开统计 |
| 12 类函数与正确率 `>=95%` | `240/240`，Wilson 95% 下界 `98.42%`；12 类函数和主要计划族均覆盖 | 当前正式基准达标 |
| 旧能力迁入新架构 | `1044/1097`，`95.17%` | 这是迁移覆盖率，不是 SQL 正确率 |
| 全量语料新后端成功 | `1083/5799` | 其余包含非法输入、缺失数据域和能力缺口，不强造 SQL |
| 19 年以上长周期加速 `>=10x` | 五类 5000 交易日工作负载全部通过，最低 `14.941x`、中位 `15.133x`，完整结果哈希一致 | 达标 |
| SQL 执行 `<10s` | 分层性能矩阵 `48/48`，最大 P95 `2969.521ms` | 对已纳入矩阵的工作负载达标 |
| 编译 P95 `<50ms` | 48 条分层语句、1440 个样本，P95 `44.115ms` | 达标 |
| 新指标/新函数零核心改动 | 配置式指标与受类型约束表达式树；盲测保持核心树哈希不变 | `relative_gap` 真实 Doris `5573/5573` 行集一致 |
| 回归质量 | `1147 passed`，官方正例/负例 `37/37 + 37/37`，warning `0` | 当前门禁通过 |

机器可读口径见 [evidence_metadata.json](submission_artifacts/evidence_metadata.json)，详细评分映射见 [赛题要求与验收](docs/赛题要求与验收.md)。

## 编译架构

```text
官方 DSL
  -> ANTLR4 Frontend + Source Map
  -> Immutable Typed AST
  -> Semantic Policy / Domain Binder
  -> Canonical Logical IR
  -> Equivalence Rewrite Rules
  -> Physical Candidate Planner + Cost/Risk Selector
  -> Validated Physical IR
  -> SQLGlot Doris AST / SQL
  -> Doris Execute / Explain / Profile
  -> Independent Oracle / Evidence Contract
```

正式实现位于 `src/findsl/official/`。旧手写管道仅保留为兼容入口和差分基线，并被 import-linter 禁止反向进入正式编译器。ANTLR4 负责文法与错误位置，SQLGlot 负责 SQL AST 和 Doris 方言渲染，Apache Doris 负责数据库内执行优化；项目自研部分集中在金融 DSL 语义、关系 IR、候选规划、成本风险和证据合同。

每次正式编译都会生成结构化 `FINDSL EXPLAIN`，按 Parser、Semantic、Logical IR、Rewrite、Route、Doris SQL 六个阶段记录产物标识。`AdaptiveRoutePlanner` 将实际物理决策统一投影为 `RAW / PARTITION / MV / PREFIX` 四类路由；未生成或不满足等价条件的候选仍会显示原因码，但不会被伪装成可执行路径。金融规则来自版本化 `FinancialRuleCatalog`，优化规则具有前置条件、语义不变量、回退和验证契约。

架构细节见 [架构设计](docs/架构设计.md)，全部目录职责见 [PROJECT_INDEX.md](PROJECT_INDEX.md)。

## 快速开始

建议使用 Python 3.11；最低支持 Python 3.9。

```powershell
python -m pip install -e ".[dev]"
python scripts/generate_antlr.py --check
python -m ruff check .
lint-imports
python -m pytest
```

编译一条官方 DSL：

```powershell
$env:PYTHONPATH = "src"
python -m findsl.cli official-slot-backend `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" --json
```

查看完整编译解释并导出 Markdown：

```powershell
python -m findsl.cli official-explain `
  "indicator('', '', '成交量', '近5000日', '', 'SUM', '') > 10000000"

python -m findsl.cli official-result `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" `
  --output output/findsl-result.md
```

启动 Web 演示：

```powershell
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
```

浏览器访问 `http://127.0.0.1:8765`。完整命令和 Doris 启动流程见 [运行测试与 Doris](docs/运行测试与Doris.md)。

Windows 一键启动 Doris、样例数据和容器化 Demo：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_stack.ps1
```

网络需要本机代理时可追加 `-ProxyUrl http://127.0.0.1:7897`；脚本会自动换成 Docker Desktop 可访问的宿主机地址，代理只参与镜像构建。

## 数据模式

```powershell
# 仅依赖赛题方数据，适合评委离线复现
$env:FINDSL_DATA_PROFILE = "official_only"

# 使用已登记、已版本化的公开关系数据
$env:FINDSL_DATA_PROFILE = "enriched_public"
```

外部数据不会在在线编译请求中临时抓取。只有来源、许可、快照日期、成员完整性和历史有效期可说明的数据才能进入正式目录；无法确定的数据返回结构化诊断，不用空集合、全市场或模糊名称映射伪造成功。详见 [数据与证据](docs/数据与证据.md)。

## 仓库导航

| 路径 | 内容 |
| --- | --- |
| `src/findsl/official/` | 正式 ANTLR/IR/优化/物理规划/Doris 后端 |
| `src/findsl/compat/` | 兼容和差分基线，不承接新语义 |
| `grammar/OfficialSlot.g4` | 官方 DSL 唯一文法源 |
| `configs/official/` | 指标、函数、物理策略、数据源和证据合同 |
| `data/official_correctness/` | 独立 reference SQL 正确率基准 |
| `data/official_performance/` | 分层性能矩阵定义 |
| `data/hero/` | 复杂 Hero Query 与独立 Reference SQL |
| `deploy/` | API 与 Doris 部署资产 |
| `scripts/` | 生成、同步、装载、评测和证据采集脚本 |
| `tests/` | 单元、集成、架构边界和证据合同测试 |
| `submission_artifacts/` | 精简后的当前证据快照，不含 PPT、视频和大量截图 |

## 文档

- [文档导航](docs/README.md)
- [赛题要求与验收](docs/赛题要求与验收.md)
- [架构设计](docs/架构设计.md)
- [数据与证据](docs/数据与证据.md)
- [运行测试与 Doris](docs/运行测试与Doris.md)
- [开发路线](docs/开发路线.md)

历史阶段报告、旧方案、操作手册、PPT、科研图和截图视频已从当前树移除。需要追溯时使用 Git 历史；功能冻结后再按最终 HEAD 生成一次正式展示材料，避免旧数字和当前代码混用。

## 开发原则

1. 以能力族为开发单位，不按 Excel 行号或完整 DSL 文本打补丁。
2. 先判定问题属于语法、类型、语义、关系表达、物理规划、数据还是非法输入，再修改对应层。
3. 等价规则只生成语义等价候选，成本模型只负责选择，二者保持分离。
4. 数据不可用时 fail closed；不通过猜测、空结果或假字段提高表面覆盖率。
5. 每项“完成”必须同时具备实现、回归、真实 Doris 执行、结果集对照和版本化证据。
