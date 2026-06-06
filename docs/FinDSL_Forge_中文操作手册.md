---
title: "FinDSL Forge 中文操作手册"
subtitle: "行情选股 DSL 到高性能 Doris SQL 自动化编译系统"
author: "FinDSL Forge Team"
date: "2026-06-07"
lang: zh-CN
---

# FinDSL Forge 中文操作手册

本文档面向 FinDSL Forge 项目的安装、启动、功能使用、Doris 证据采集和提交前验收。它更接近一份可执行的软件操作手册，而不是架构白皮书；读者可以按章节完成环境检查、命令行编译、Web Demo 演示、SQL 等价验证、Doris 规模证据采集和提交包整理。

FinDSL Forge 是面向中国研究生金融科技创新大赛赛题 19 的工程原型。系统把金融行情选股 DSL 编译为 Apache Doris SQL，并用独立参考语义、SQLite 执行器和 Doris 规模证据验证正确性与性能。项目不把数据库执行权交给大模型；中文自然语言或 LLM 只负责产生候选 DSL，候选表达式仍必须经过确定性编译器、SQL 安全检查和参考等价验证。

## 第1章 引言

### 1.1 编写目的

本手册用于指导评审、答辩人员、开发维护人员和项目交接人员正确运行 FinDSL Forge。阅读者可以根据本文完成从代码仓库到本地可运行系统的准备，也可以在答辩前使用本文检查核心证据是否仍然有效。

文档重点回答四个问题：项目是什么，如何启动，如何使用主要功能，如何验证赛题要求。涉及尚需人工补充的信息，文档会使用 `【待补充】` 标记，不虚构账号、密钥、线上地址或未确认的运行参数。

### 1.2 项目背景

赛题 19 要求构建从行情选股 DSL 到高性能 Doris SQL 的自动化编译系统，核心关注语义解析、逻辑等价重写、声明式配置扩展、长周期查询加速和可复核工程交付。FinDSL Forge 的设计路线是先限定 DSL 的合法表达，再把表达编译为 Doris 友好的 SQL，最后用独立 reference evaluator 与真实 Doris evidence 证明结果可信。

当前项目已形成完整证据链。最新提交快照中，`submission_readiness` 显示核心门禁全部通过，官方风格正例 `37/37`、负例 `37/37`，全量 pytest 为 `184 passed`，Doris 规模证据保留 5,000,000 行数据和 36.24x 长窗口加速证明。

### 1.3 适用对象

| 对象 | 使用重点 | 建议阅读章节 |
|---|---|---|
| 评审专家 | 了解系统功能、演示入口、证据来源 | 第2章、第5章、第8章、第10章 |
| 答辩人员 | 按顺序启动 Demo、展示正负例和性能证据 | 第4章、第5章、第6章、第10章 |
| 开发维护人员 | 安装环境、运行测试、维护配置和脚本 | 第3章、第4章、第7章、第9章 |
| 项目交接人员 | 确认文件结构、回溯方式和交付资产 | 第2章、第8章、第11章、附录 |

### 1.4 文档范围

本文档覆盖本地 Windows 环境下的项目运行、CLI 操作、Web Demo 操作、Doris 部署证据路径、提交前 readiness 检查和常见问题处理。文档不替代 Apache Doris 官方运维手册，也不提供线上生产集群的账号、密码、主机地址或安全策略。这些信息应由实际部署环境负责人补充。

### 1.5 术语说明

| 术语 | 说明 |
|---|---|
| DSL | Domain Specific Language，本文中特指受限的金融选股表达语言。 |
| AST | Abstract Syntax Tree，语法解析后得到的抽象语法树。 |
| Doris SQL | 面向 Apache Doris 执行环境生成的 SQL。 |
| Prefix-Sum | 前缀和优化路径，用于加速长窗口滚动 SUM 查询。 |
| readiness | 提交前总验收报告，整合测试、等价验证、Doris 证据和 Git 状态。 |
| NL2DSL | 从中文自然语言需求生成候选 DSL 的辅助入口。 |

## 第2章 软件概述

### 2.1 软件简介

FinDSL Forge 是一套面向行情选股场景的 DSL 编译与验证系统。用户可以输入 FinDSL 表达式，系统会完成词法分析、语法解析、强类型语义校验、Doris SQL 生成、优化解释、SQL 安全检查和结果等价验证。系统同时提供命令行工具和本地 Web Demo，便于开发测试和现场演示。

项目面向的典型问题是：分析师希望表达“连续 3 天主力净流入为正后按换手率排名”或“日期区间内近 3 日成交量累计大于阈值”，但直接手写 SQL 容易出现窗口语义、日期裁剪、辅助表 join 和性能路径错误。FinDSL Forge 把这些细节收敛到编译器和配置中，使业务表达、SQL 生成和性能优化能够被统一管理。

### 2.2 主要功能

系统当前支持的主要功能如下：

- 解析 `filter`、`then`、`rank`、`indicator`、`market`、`date_between` 等基础表达。
- 支持 `CONS`、`EXIST`、`MA`、`SUM`、`MAX`、`MIN`、`RET` 等窗口和收益率函数。
- 支持 `&`、`^`、`|` 跨市场布尔组合，支持 `top`、`bottom`、`percent` 排名截断。
- 基于 `configs` 中的表、指标和函数配置完成业务规则解耦。
- 对 prefix-sum 可优化的滚动 SUM 生成前缀表访问 SQL。
- 提供 Pandas reference evaluator 与 SQLite 执行器，用于本地语义等价检查。
- 提供 Web Demo 展示 DSL、AST、SQL、Explain、Rows、Evidence 和 Diagnostic。
- 提供 Doris schema、sample data、prefix table build 和 smoke query 资产。
- 提供 readiness 报告，集中检查 pytest、官方套件、Doris evidence、真实行情样本和 Git 状态。

### 2.3 软件特点

FinDSL Forge 的核心特点是“确定性编译 + 可验证优化 + 受控 AI 辅助”。系统不会接受 LLM 直接生成 SQL，也不会把裸 SQL 交给 Doris 执行。所有表达都必须经过 DSL 解析、语义验证、SQL 生成、Doris SQL shape 检查和 reference equivalence。

在性能上，系统对长窗口滚动 SUM 提供 prefix-sum rewrite。对于配置了 `supports_prefix_sum` 的指标，编译器会把窗口聚合改写为前缀表查找或热点窗口列访问。当前 Doris evidence 中，5,000,000 行规模数据上的 120 日成交量路径达到 36.24x 加速，超过赛题 10x 目标。

### 2.4 总体运行流程

系统运行流程可以概括为：

```text
中文需求或 DSL
  -> 候选 DSL 生成或直接输入
  -> Lexer / Parser
  -> Typed AST
  -> Semantic Analyzer
  -> SQL Generator
  -> Doris SQL Validator
  -> SQLite/Doris 执行或 Evidence 采集
  -> Readiness / Defense Package
```

用户在日常操作中不需要手动调用每一个内部模块。命令行和 Web Demo 已经把常用路径封装成 `compile`、`verify-sql`、`suggest-dsl`、`official-suite`、`defense-package`、`readiness-report` 等命令。

### 2.5 目录结构

| 路径 | 作用 |
|---|---|
| `src/findsl` | 编译器、CLI、Demo、Doris evidence、readiness 等核心代码。 |
| `configs` | 函数、指标和表的声明式配置。 |
| `data/samples` | 本地测试用样本数据、官方风格用例和 LLM 候选示例。 |
| `data/real_samples` | 公开行情小样本，用于业务可信度演示。 |
| `deploy/doris` | Doris 建表、样本导入、前缀表构建和 smoke query SQL。 |
| `docs` | 架构说明、Doris runbook、中文综合指南和本操作手册。 |
| `reports` | 本地生成的评估、等价验证、readiness 和 Doris evidence 报告。 |
| `submission_artifacts` | 提交包素材、截图、视频和已导出的证据快照。 |
| `tests` | pytest 回归测试。 |

### 2.6 用户角色说明

FinDSL Forge 没有传统业务系统中的登录账号和权限体系。本地演示版本默认由操作者直接在命令行或 Web Demo 中使用，因此“角色”更多体现为使用职责，而不是系统内置权限。为了避免答辩和交接时职责混乱，建议按以下方式理解不同角色。

评审或验收人员主要关注结果是否可信。他们通常不需要修改配置，也不需要重新采集 Doris 规模数据，只需要能够查看 Demo、阅读 evidence snapshots、确认 readiness 结论，并能追溯关键指标来自哪个文件。文档中涉及“如何证明”的内容，主要服务于这一类读者。

答辩人员主要关注演示是否顺畅。他们需要提前熟悉正例、负例、prefix-sum 示例和 readiness 报告的展示顺序。答辩人员不应在现场临时修改 DSL 语法、指标配置或 Doris 表结构；这些动作风险较高，应在演示前完成并重新跑完整验收。

开发维护人员负责代码、配置、测试和证据更新。他们需要理解 `src/findsl` 的模块边界，知道指标配置与核心编译器代码的关系，也要能处理 pytest、official suite、Doris evidence 和文档导出中出现的问题。若后续扩展新指标、新函数或新样本，应由该角色负责补齐测试和文档。

项目交接人员关注材料完整性。他们需要确认 GitHub、离线 bundle、DOCX/PDF 文档、截图、视频和 evidence snapshots 都已经同步到同一版本。项目进入最终提交阶段后，交接人员应优先保证“代码版本、报告数字、演示材料”三者一致，而不是继续增加新功能。

## 第3章 运行环境

### 3.1 硬件环境

本地开发和演示不需要特殊硬件。普通 Windows 开发机即可运行 CLI、pytest、SQLite 验证和 Web Demo。Doris 5M 规模证据采集依赖 Docker Desktop、WSL2 和本机资源，建议至少准备较充足的内存和磁盘空间。精确硬件配置与 Docker 分配资源应按实际机器补充：`【待补充】`。

### 3.2 软件环境

| 软件 | 用途 | 当前建议 |
|---|---|---|
| Windows PowerShell | 执行项目脚本 | 使用普通 PowerShell 即可。 |
| Python 3.9+ | 运行项目和测试 | 项目 `pyproject.toml` 要求 `>=3.9`。 |
| pytest | 回归测试 | 开发环境依赖。 |
| pandas | reference evaluator 和验证 | 可通过项目开发依赖安装。 |
| Git | 版本管理和回溯 | 必需。 |
| Docker Desktop + WSL2 | Doris 本地环境 | 采集真实 Doris 证据时需要。 |
| MySQL 客户端 | 连接 Doris 9030 查询端口 | 用于执行 Doris SQL。 |
| pandoc / LibreOffice | 导出文档 | 本手册导出 DOCX/PDF 使用。 |

### 3.3 网络环境

本地 CLI、pytest、SQLite 验证和 Web Demo 不依赖外网。拉取 Docker 镜像、刷新 Eastmoney 真实行情样本、访问 GitHub 或调用外部 LLM provider 时可能需要网络。若机器通过本地代理访问外网，可以使用 `http://127.0.0.1:7897` 作为代理参数。

### 3.4 外部依赖与密钥

项目默认可以在无 LLM 密钥的情况下运行。`llm-suggest-dsl` 是可选功能，需要 OpenAI-compatible provider 的模型名、base URL 和 API key。出于安全原因，本文档不记录任何真实密钥。需要使用真实 provider 时，由操作者在当前 shell 中设置环境变量：

```powershell
$env:FINDSL_LLM_API_KEY="<your key>"
$env:FINDSL_LLM_MODEL="<provider-model>"
$env:FINDSL_LLM_BASE_URL="https://api.openai.com/v1"
```

### 3.5 环境自检方法

首次接手项目时，不建议直接运行耗时较长的 Doris 规模脚本。更稳妥的顺序是先确认基础工具可用，再确认 Python 测试可用，最后再进入 Web Demo 和 Doris 证据路径。这样做的好处是，一旦出错，可以快速判断问题发生在工具链、Python 环境、项目代码还是外部数据库。

建议依次执行以下命令：

```powershell
python --version
git --version
pandoc --version
soffice --version
mysql --version
```

如果某个命令无法识别，先刷新 PATH：

```powershell
$machine = [Environment]::GetEnvironmentVariable('Path','Machine')
$user = [Environment]::GetEnvironmentVariable('Path','User')
$env:Path = "$machine;$user;$env:Path"
```

基础工具确认后，再进入项目根目录运行：

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_parser.py tests/test_compiler.py -q
```

这组测试耗时较短，能快速确认 parser 和 compiler 主链路是否可用。若它们通过，再运行全量 pytest 和 readiness。若一开始就直接运行完整 Doris 脚本，可能会把 Docker、网络和数据库问题混在一起，反而不利于定位。

## 第4章 安装、配置与启动

### 4.1 获取项目代码

进入项目目录：

```powershell
cd "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge"
git status --short --branch
```

正常情况下，输出应显示当前分支为 `main`，并且没有未提交修改。如果需要从 GitHub 获取最新代码，可执行：

```powershell
git pull origin main
```

如果网络需要代理，可使用：

```powershell
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 pull origin main
```

### 4.2 准备 Python 环境

如果项目没有安装为包，推荐在仓库根目录临时设置 `PYTHONPATH`：

```powershell
$env:PYTHONPATH="src"
python -m pytest -q
```

若需要完整开发依赖，可根据团队习惯使用虚拟环境安装。项目本身没有非标准运行依赖，但测试和 reference evaluator 需要 `pandas`、`pytest`。安装方式示例：

```powershell
python -m pip install -e ".[dev]"
```

执行完成后再次运行 pytest。预期结果应为全部测试通过。最新证据快照中，全量测试结果为 `184 passed`。

### 4.3 启动 Web Demo

Web Demo 用于现场演示和功能查看。启动命令如下：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1
```

脚本默认启动本地服务，通常访问地址为：

```text
http://127.0.0.1:8765
```

若端口被占用，脚本或手动命令可改用其他端口：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8766
```

启动成功后，浏览器应能看到输入区、候选 DSL、SQL、AST、Explain、Rows 和 Evidence 等内容。

【截图占位符：Web Demo 主界面】

### 4.4 退出系统

Web Demo 在当前 PowerShell 会话中运行时，可使用 `Ctrl + C` 停止。若是后台进程或旧端口残留，可通过 PowerShell 查找 Python 进程并按需关闭。关闭前请确认没有正在采集的 Doris evidence 或长时间测试任务。

### 4.5 首次运行后的验证

系统启动后，建议先做一次“轻量闭环验证”。这个验证不依赖 Doris，也不依赖外部 LLM provider，适合作为安装完成后的第一道确认。

1. 在浏览器打开 Web Demo。
2. 使用默认中文请求或输入“筛选A股连续三天主力净流入为正并按换手率排名前一百”。
3. 查看系统生成的候选 DSL，确认候选表达式通过验证。
4. 切换到 SQL 和 Explain 区域，确认 SQL、AST 和规则记录正常显示。
5. 切换到 Evidence 或 Rows 区域，确认验证结果为 PASS。

完成上述步骤后，可以认为本地 Demo 主链路已经可用。如果页面能打开但分析失败，优先查看启动窗口中的报错；如果页面无法打开，优先检查端口、进程和防火墙；如果只有 verification 失败，则查看样本数据和 `PYTHONPATH` 是否正确。

【截图占位符：首次运行验证通过页面】

## 第5章 系统界面说明

### 5.1 主界面布局

Web Demo 的主界面以任务输入和证据查看为核心。用户可以输入中文请求，也可以选择预置的官方正例、负例或真实行情样本。系统会展示候选 DSL、编译生成的 SQL、AST 结构、优化解释和验证结果。

推荐现场演示时按以下顺序讲解：先用中文需求生成候选 DSL，再打开 SQL 标签说明确定性编译路径，然后查看 Explain 标签说明优化规则，最后查看 Evidence 或 Rows 证明验证结果。这样的顺序能把“输入友好性、编译可靠性、优化可解释性、结果可信性”连成一条清晰主线。

### 5.2 DSL 与 SQL 区域

DSL 区域展示系统最终接受的 FinDSL 表达式。SQL 区域展示生成的 Doris SQL。需要注意，SQL 是编译器输出结果，不是大模型直接生成的自由文本。若 LLM 候选中包含直接 SQL，系统会返回 `UNSAFE_DIRECT_SQL` 类型的拒绝结果。

【截图占位符：DSL 与 Doris SQL 展示区域】

### 5.3 AST 与 Explain 区域

AST 区域用于查看语法树结构，适合解释系统如何理解 DSL。Explain 区域展示编译器应用或跳过的规则，例如 `PREFIX_SUM`、`DATE_RANGE_PUSHDOWN`、`ROLLING_BOOLEAN`、`RETURN_RATE`、`FILTER_OUTER_WHERE` 和 `DORIS_SQL_VALIDATION`。这些 explain 记录是答辩中的重要证据，它们说明优化不是黑盒行为。

### 5.4 Diagnostic 区域

当输入非法 DSL、未知指标、错误窗口或不安全 SQL 时，Diagnostic 区域会显示稳定错误码和修复建议。现场可以故意输入：

```text
filter(indicator("clos") > 10)
```

系统应提示未知指标，并给出接近 `indicator("close")` 的修复建议。这个演示能证明系统不仅能处理成功路径，也能处理用户错误和隐藏测试中的异常输入。

### 5.5 系统提示信息与状态判断

Web Demo 中的提示信息主要分为三类。第一类是正常结果，例如候选 DSL 已验证、SQL/reference 一致、optimizer rule applied。看到这类提示时，可以继续查看 SQL、AST 和 Rows。第二类是诊断信息，例如未知指标、非法窗口、非法 rank 参数或直接 SQL 被拒绝。诊断信息不应被视为程序崩溃，它是系统有意设计的可恢复失败路径。第三类是运行时错误，例如样本数据缺失、服务端异常或外部 provider 调用失败，这类问题需要回到命令行查看日志。

答辩时应主动展示一次诊断路径。许多项目只展示成功样例，评委很难判断系统面对错误输入时是否可靠。FinDSL Forge 的诊断区能把错误码和修复建议展示出来，说明系统对无效 DSL 有明确边界，不会把错误表达继续编译成危险 SQL。

如果提示中出现 `UNSAFE_DIRECT_SQL`，说明候选内容看起来像 SQL，而不是受控 DSL。正确处理方式不是放行该内容，而是要求用户或 LLM 重新给出 FinDSL 表达式。金融场景中，拒绝直接 SQL 是安全设计的一部分。

## 第6章 功能操作说明

### 6.1 编译 DSL 为 Doris SQL

最直接的操作是把 DSL 编译为 Doris SQL。进入仓库根目录后执行：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
```

预期结果是输出一条包含窗口函数的 Doris SQL，并展示编译耗时、trace 或 explain 信息。若希望查看 JSON 结构，可增加 `--json`：

```powershell
python -m findsl.cli compile 'filter(market("A") ^ indicator("close") > 10)' --json
```

该示例用于验证跨市场布尔异或 `^`。SQL 中应出现 `CASE WHEN ... THEN 1 ELSE 0 END <> ...` 形式的空值安全异或表达。

### 6.2 验证 SQL 与参考语义一致

编译成功不等于语义一定正确。项目提供 `verify-sql` 命令，将编译生成的 SQL 结果与 Pandas reference evaluator 的结果进行比较：

```powershell
python -m findsl.cli verify-sql 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
```

预期结果中 `passed` 应为 `true`，并且 missing/extra keys 为空。若不一致，应优先排查 DSL 语义、SQL generator、样本数据和 prefix table 构建逻辑，而不是直接修改测试预期。

### 6.3 使用中文需求生成候选 DSL

系统支持确定性中文模板生成 DSL 候选。示例：

```powershell
python -m findsl.cli suggest-dsl '筛选A股连续三天主力净流入为正并按换手率排名前一百' --data-dir data/samples --json
```

预期输出包括候选 DSL、验证状态和 SQL/reference 结果。模板覆盖低价排名、换手率百分比、B 股均量、日期窗口、主力净流出、收益率、前缀和日期裁剪等官方风格场景。模板不是随意文本匹配，而是服务于可验证 DSL 候选。

### 6.4 验证 LLM 候选安全性

离线 LLM 候选验证命令如下：

```powershell
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --data-dir data/samples --json
```

示例响应文件中包含一个合法 DSL、一个拼错指标和一个直接 SQL。预期结果是合法 DSL 被接受，拼错指标返回诊断，直接 SQL 被拒绝。该功能适合答辩时说明：系统可以利用大模型辅助输入，但不会放弃金融系统需要的安全边界。

### 6.5 运行官方风格覆盖套件

官方风格套件用于证明系统覆盖代表性赛题用例和负例诊断：

```powershell
python -m findsl.cli official-suite --output reports/official_suite_report.md --json
```

或者使用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\official_suite.ps1
```

最新证据显示正例 `37/37`、负例 `37/37`。若该命令失败，应查看 `reports/official_suite_report.md` 中失败用例的 missing SQL fragment、missing trace fragment 或诊断码差异。

### 6.6 生成答辩证据包

答辩证据包把可演示动作映射到得分点：

```powershell
python -m findsl.cli defense-package --output reports/defense_package.md --json
```

输出文件 `reports/defense_package.md` 会列出 NL2DSL、LLM 安全环、prefix-sum 正例、诊断负例、真实行情样本、配置扩展和官方套件等检查项。现场准备时建议先读该报告，再安排演示顺序。

### 6.7 使用真实行情小样本

真实行情小样本位于 `data/real_samples/eastmoney_a_share_sample`。它用于说明系统能够处理公开 A 股行情字段，而不是只在人工构造的小样本上运行。使用该样本时，应明确说明它服务于业务可信度展示，不承担性能证明职责。

运行示例：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample --json
```

预期结果是 SQL/reference 等价验证通过，并返回真实行情日期和股票代码对应的结果行。若样本文件缺失，应检查 `daily_quote.csv`、`stock_universe.csv`、`money_flow.csv` 和 `queries.jsonl` 是否存在。若需要刷新公开行情原始数据，可运行：

```powershell
python .\scripts\fetch_real_market_sample.py --refresh --proxy "http://127.0.0.1:7897"
```

刷新前应确认网络代理可用。刷新后需要重新运行真实行情样本测试和 readiness，避免文档中的结果与数据文件不一致。

### 6.8 运行 prefix-sum 本地基准

prefix-sum 本地基准用于检查优化路径的正确性和计划形态。它不是最终 Doris 规模性能证明，但能在没有 Doris 环境时快速确认同一 DSL 的 baseline 和 optimized 两条 SQL 是否语义一致。

运行命令：

```powershell
python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.md
```

报告中应同时出现 baseline window 与 optimized prefix-sum 相关信息，并说明 optimized 结果与 Pandas reference、baseline SQL 一致。由于 SQLite 和 Doris 的执行模型不同，本地 SQLite timing 只适合作为回归信号，不应当作为比赛性能结论。正式性能结论必须以 Doris evidence 为准。

### 6.9 处理负例与修复建议

负例操作不是为了“制造错误”，而是为了证明系统边界清晰。建议至少验证以下几类负例：未知指标、非法窗口、非法日期、rank 参数冲突、直接 SQL 候选和裸字段绕过。命令行可以使用：

```powershell
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json
```

预期结果中应包含稳定诊断码和修复建议。若诊断只返回普通异常堆栈，说明错误处理链路出现退化，应优先修复 diagnostics 层。对于竞赛项目而言，负例体验本身就是工程成熟度的一部分。

## 第7章 Doris 环境与性能证据操作

### 7.1 生成 Doris SQL 资产

Doris 部署资产由项目脚本生成：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
```

生成结果位于 `deploy/doris`：

```text
01_schema.sql
02_sample_data.sql
03_build_prefix_tables.sql
04_smoke_queries.sql
```

这些文件用于 smoke-test 和 Doris evidence 采集。schema 中包含月度 `trade_date` 自动分区和基于 `ts_code` 的 colocate 分布设计，目的是让日期裁剪和前缀表 join 有可见的物理设计支撑。

### 7.2 在 Doris 中执行 SQL 文件

使用 MySQL 兼容客户端连接 Doris 查询端口，按顺序执行：

```powershell
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/01_schema.sql
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/02_sample_data.sql
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/03_build_prefix_tables.sql
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/04_smoke_queries.sql
```

其中 `<fe_host>`、`<query_port>`、`<user>` 由实际 Doris 环境决定。若使用本地 Docker Doris，通常 FE MySQL 协议端口为 `9030`，但最终以本机实际配置为准。

### 7.3 采集 Doris 集群证据

当 schema、数据和 prefix table 都准备完成后，运行：

```powershell
$env:DORIS_HOST="127.0.0.1"
$env:DORIS_PORT="9030"
$env:DORIS_USER="root"
$env:DORIS_DATABASE="findsl_demo"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

该脚本会生成：

```text
reports/doris_cluster_evidence.md
reports/doris_cluster_evidence.json
```

readiness 只有在 baseline 和 optimized 均执行成功、行数一致、baseline 含窗口计划、optimized 含 prefix table、加速达到 10x 阈值时，才会认为 Doris-scale performance proof 通过。

### 7.4 一键准备本地规模证据

如果已经安装 WSL2、Docker Desktop 和 Doris 相关镜像，可以使用端到端脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_doris_scale_evidence.ps1 -ProxyUrl "http://127.0.0.1:7897"
```

脚本会启动本地 Doris compose 集群、生成确定性规模 CSV、Stream Load 到 Doris、构建前缀表、采集 evidence 并重新运行 readiness。这个路径耗时较长，适合提交前重新采集性能证据，不建议在正式答辩现场临时运行。

### 7.5 性能结论的表达边界

当前 36.24x 是 5,000,000 行数据、120 日成交量滚动 SUM、prefix 热点路径上的真实 Doris evidence。答辩中应准确说明它证明的是长窗口 prefix-sum 路径具备显著加速能力，不能泛化为所有查询都会提升 36 倍。这样的边界说明更专业，也更容易经受追问。

### 7.6 Doris 物理设计检查

在正式采集 evidence 前，建议使用 Doris 客户端检查表结构和物理布局。这样可以确认 schema 不是只停留在文件中，而是真的在 Doris 中按预期创建。

```sql
USE findsl_demo;

SHOW CREATE TABLE dwd_stock_daily_quote;
SHOW CREATE TABLE dwd_stock_daily_quote_prefix;
SHOW CREATE TABLE dwd_stock_money_flow;
SHOW CREATE TABLE dwd_stock_money_flow_prefix;

SHOW PARTITIONS FROM dwd_stock_daily_quote;
SHOW PARTITIONS FROM dwd_stock_daily_quote_prefix;

SHOW PROC '/colocation_group';
```

检查重点包括：基础表和前缀表是否都存在，`trade_date` 是否使用自动分区，`ts_code` 分布是否与 prefix join 路径匹配，colocate group 是否稳定，prefix table 是否在 base table 加载后重建。若这些条件不满足，即使 SQL 能执行，性能证据也可能缺少说服力。

### 7.7 Doris 证据异常排查

如果 `collect_doris_evidence.ps1` 失败，应先区分连接错误、SQL 执行错误、行数不一致和加速不达标四类问题。连接错误通常与 FE 地址、端口、MySQL 客户端或容器状态有关；SQL 执行错误通常与 schema 未创建、表名不一致或 prefix table 未构建有关；行数不一致属于语义风险，应优先检查 prefix table 的 `row_no` 和数据加载顺序；加速不达标则需要检查数据量、缓存、分区裁剪和物理布局。

不要在行数不一致时继续讨论性能。性能比较的前提是 baseline 和 optimized 语义一致。readiness 也按这个原则设计，只有 row-count parity、plan-shape marker 和 10x speedup 同时满足，Doris-scale performance proof 才会通过。

## 第8章 数据、报告与提交资产管理

### 8.1 样本数据

`data/samples` 是本地测试样本，包含日行情、资金流、股票市场归属、官方正负例和 LLM 候选响应示例。它用于快速验证编译语义，不用于证明 Doris 大规模性能。

`data/real_samples/eastmoney_a_share_sample` 是公开行情小样本，用于展示系统可以处理真实 A 股字段。该样本适合增强业务可信度，但不应与 5M Doris 性能证据混为一谈。

### 8.2 报告文件

常用报告包括：

| 报告 | 生成方式 | 用途 |
|---|---|---|
| `reports/evaluation_report.md` | `scripts/evaluate.ps1` 或 readiness | 编译正确率与片段准确率。 |
| `reports/sql_equivalence_report.md` | `verify-sql` 或 readiness | SQL/reference 等价证据。 |
| `reports/official_suite_report.md` | `official-suite` | 官方风格正负例覆盖。 |
| `reports/defense_package.md` | `defense-package` | 答辩动作与得分点映射。 |
| `reports/doris_cluster_evidence.md` | `collect_doris_evidence.ps1` | 真实 Doris 计划和延迟证据。 |
| `reports/submission_readiness.md` | `submission_readiness.ps1` | 提交前总验收。 |

### 8.3 导出提交证据快照

`reports` 目录通常作为本地生成物处理，不一定全部纳入 Git。提交前应运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

该命令会把轻量证据复制到 `submission_artifacts/evidence_snapshots`，并更新 `submission_artifacts/evidence_manifest.md`。正式提交时，评审可以直接查看这些快照，而不必重新运行所有脚本。

### 8.4 截图和视频

项目已经提供 Web Demo 截图目录和一分钟演示视频目录：

```text
submission_artifacts/demo_screenshots
submission_artifacts/defense_video
```

若重新采集截图，应确保截图内容与最新 readiness 数字一致。若门户要求真人讲解或语音视频，需要在现有 MP4 基础上补充人工录制：`【待补充：最终提交平台对视频格式、时长、是否真人出镜的要求】`。

### 8.5 证据口径一致性

提交材料中最容易出现的问题不是功能缺失，而是数字口径不一致。例如 README 写 `37/37`，PPT 仍写 `36/36`；readiness 已经刷新，截图却来自旧版本；Doris evidence 的 DSL 与答辩讲述中的 DSL 不一致。评审一旦发现这类问题，会降低对整个项目证据链的信任。

因此，最终提交前应以 `submission_artifacts/evidence_snapshots/submission_readiness.md` 为准，统一检查 README、中文文档、PPT、讲稿、截图说明和视频脚本中的数字。当前关键数字包括：`184 passed`、官方正例 `37/37`、负例 `37/37`、真实行情样本 `3/3`、答辩包 `13/13`、Doris 5,000,000 行、36.24x 加速和 readiness warning count 0。

### 8.6 数据安全与敏感信息

项目文档和证据包不应包含真实 API key、数据库密码、生产主机地址或个人隐私信息。Doris evidence 采集脚本会对 inline password 做脱敏处理，但操作者仍应避免把含有敏感信息的 shell 历史、临时日志或截图放入提交材料。

如果需要在私有环境运行，建议把密钥和密码放在临时环境变量中，并在提交前检查 `reports`、`submission_artifacts` 和截图目录。对于竞赛提交版本，只应保留必要的技术证据，不应暴露与评审无关的访问凭据。

## 第9章 系统维护与配置扩展

### 9.1 指标配置

指标配置位于 `configs/indicators.json`。新增普通指标时，应优先通过配置声明指标名、表名、列名、类型和是否支持 prefix-sum。赛题要求“新指标/新函数核心编译代码 0 行改动”时，项目用 config-only extension evidence 证明常见指标扩展可以不改编译器内核。

修改配置后，应至少运行：

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_config_extension.py tests/test_official_suite.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
```

### 9.2 函数配置

函数配置位于 `configs/functions.json`。当前包括 `filter`、`then`、`rank`、`indicator`、`market`、`date_between`、`CONS`、`EXIST`、`MA`、`SUM`、`MAX`、`MIN`、`RET` 等。函数如果涉及新的语义类别或 SQL rewrite，通常需要新增语义分析、SQL 生成和 reference evaluator 测试，不能只改配置。

### 9.3 Git 回溯与备份

查看当前版本：

```powershell
git status --short --branch
git log --oneline -5
```

创建离线 bundle：

```powershell
$bundleDir = "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\git_bundles"
New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bundle = Join-Path $bundleDir "findsl-forge_git_backup_$stamp.bundle"
git bundle create $bundle --all
git bundle verify $bundle
```

推送 GitHub 时，如果当前网络需要代理：

```powershell
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push origin main
```

### 9.4 日常维护建议

日常维护应遵循“小步修改、及时验证、证据同步”的原则。每次只修改一个清晰范围，例如新增指标、补充官方正例、调整 Demo UI 或更新 Doris 证据。修改后先运行相关最小测试，再运行全量 pytest，最后运行 readiness。这样可以避免多个问题叠在一起，导致定位困难。

如果修改涉及 DSL 语法，应同时检查 lexer、parser、semantic、sqlgen、reference 和 official suite。语法层新增能力如果没有 reference evaluator 支撑，很容易出现“能编译但无法证明正确”的问题。如果修改涉及性能优化，应同时检查 baseline SQL、optimized SQL、plan shape 和 row-count parity。

### 9.5 配置扩展注意事项

配置扩展要分清“新增指标”和“新增函数”的差异。新增指标通常可以通过 `configs/indicators.json` 完成，并借助已有 `indicator()`、窗口函数和 rank 逻辑运行。新增函数往往涉及新返回类型、新语义约束或新 SQL rewrite，因此通常需要改代码和测试。

新增 prefix-sum 指标时，必须确认前缀表 schema、prefix column、row number 和基础表日期骨架一致。对于资金流这类稀疏辅助表，前缀表应基于日行情交易日骨架构建，再左连接辅助值，避免因为缺失行导致滚动窗口错位。

## 第10章 提交前验收流程

### 10.1 一键 readiness

提交前运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
```

理想结果如下：

```text
Blocking gates passed: True
Warning count: 0
Pytest regression suite: PASS
Official-style coverage suite: positive 37/37, negative 37/37
Doris-scale performance proof: PASS
Git rollback cleanliness: PASS
```

如果 warning 不为 0，应根据报告定位原因。常见 warning 包括 Git 工作区未提交、Doris evidence 缺失或规模报告缺失。不要在 warning 未解释清楚时提交最终材料。

### 10.2 最终提交检查清单

- 运行 `python -m pytest -q`，确认无失败。
- 运行 `scripts/submission_readiness.ps1`，确认核心 gate 通过。
- 运行 `scripts/export_submission_artifacts.ps1`，刷新证据快照。
- 检查 `README.md`、中文手册、PPT、演示稿中的关键数字一致。
- 检查 `submission_artifacts/demo_screenshots` 与当前界面一致。
- 检查 Git 工作区干净，提交并推送到远端。
- 生成并验证 Git bundle。
- 根据比赛平台要求上传代码、文档、视频和其他附件。

### 10.3 答辩演示建议

建议演示顺序为：

1. 打开 Web Demo，输入中文需求，生成并验证候选 DSL。
2. 展示 SQL 标签，说明系统生成的是 Doris SQL，不是 LLM 直接 SQL。
3. 展示 AST 与 Explain，说明语法树、日期下推和 prefix-sum 规则。
4. 切换到 official positive 的 prefix-sum 示例，展示前缀表路径。
5. 切换到 negative 示例，展示未知指标诊断和修复建议。
6. 打开 readiness 或 evidence snapshot，展示 `37/37`、`184 passed`、Doris 10x+ 证据和 warning 0。

答辩时不要把所有命令都现场运行一遍。现场重点是说明主线和证据，长耗时 Doris 重采集应作为已生成报告展示。

### 10.4 验收判定标准

项目是否可以进入正式提交，建议按“可运行、可解释、可验证、可回溯”四个标准判断。可运行指 CLI、Web Demo 和核心脚本可以在本地环境启动；可解释指 AST、Explain、Diagnostic 和文档能说明系统行为；可验证指 pytest、official suite、equivalence、Doris evidence 和 readiness 均有报告；可回溯指 GitHub、commit hash 和 bundle 能恢复当前版本。

若四个标准中任何一个不满足，都不建议把项目描述为最终可提交状态。比如 Web Demo 能跑但 readiness warning 未处理，只能说明演示可用，不能说明提交证据完整；Doris evidence 存在但 Git 工作区脏，也不能说明版本可回溯。

### 10.5 提交材料组织建议

正式提交时建议按以下逻辑组织附件：代码仓库或压缩包、中文操作手册、综合白皮书、readiness 快照、Doris evidence、Demo 截图、演示视频和答辩 PPT。操作手册负责告诉评审“怎么运行”，综合白皮书负责解释“为什么这样设计”，readiness 和 evidence 负责证明“结果是否可信”。

如果提交平台限制文件数量，应优先保留代码、PDF 文档、readiness 快照和演示视频。DOCX 可作为可编辑源文件一并提交；Markdown 可保留在仓库中，便于后续修改和差异追踪。

## 第11章 常见问题与处理方法

### 11.1 PowerShell 找不到 Python、pandoc 或 soffice

先刷新 PATH：

```powershell
$machine = [Environment]::GetEnvironmentVariable('Path','Machine')
$user = [Environment]::GetEnvironmentVariable('Path','User')
$env:Path = "$machine;$user;$env:Path"
$env:TESSDATA_PREFIX = [Environment]::GetEnvironmentVariable('TESSDATA_PREFIX','User')
```

刷新后重新执行命令。如果仍不可用，再检查工具是否安装。

### 11.2 pytest 失败

先阅读失败用例名和错误堆栈，不要直接修改断言。若失败集中在 SQL 等价或 official suite，应查看对应 DSL、生成 SQL、reference result 和缺失 fragment。修复后重新运行最小相关测试，再运行全量 pytest。

### 11.3 Web Demo 端口占用

更换端口启动：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8766
```

如果旧进程仍占用端口，关闭对应 Python 进程后再启动。

### 11.4 Doris 连接失败

检查 Docker Desktop、WSL2、Doris FE/BE 容器状态、FE 查询端口、MySQL 客户端路径和环境变量。确认后使用 MySQL 客户端手动连接：

```powershell
mysql -h 127.0.0.1 -P 9030 -u root
```

如果连接成功但 readiness 仍提示 Doris evidence 缺失，重新运行 `collect_doris_evidence.ps1` 并查看 `reports/doris_cluster_evidence.md` 中的错误信息。

### 11.5 LLM provider 调用失败

LLM provider 是可选能力，不影响核心提交路径。若调用失败，检查 `FINDSL_LLM_API_KEY`、`FINDSL_LLM_MODEL`、`FINDSL_LLM_BASE_URL` 和网络代理。答辩中可以使用离线 `validate-llm-candidates` 证明安全环，不必依赖现场外部网络。

### 11.6 readiness 出现 Git rollback warning

如果 readiness 报告中 `Git rollback cleanliness` 为 WARN，通常表示工作区存在未提交修改。这在开发过程中很常见，但不适合最终提交。处理方式是先查看：

```powershell
git status --short
```

确认每个修改文件是否属于本次任务。需要保留的修改应提交；无关临时文件应移出提交范围或加入合理忽略规则。不要为了让报告变绿而随意删除不了解的文件，尤其是在多人协作或用户手动修改过文件的情况下。

### 11.7 文档导出乱码或 PDF 异常

如果 DOCX 正常但 PDF 出现乱码，优先检查 LibreOffice 字体和编码环境。本文档使用 Markdown -> DOCX -> PDF 的转换路径，中文字体通常由系统字体和 LibreOffice 共同决定。导出后应使用 `pdfinfo` 检查页数，并用 `pdftoppm` 抽样渲染前几页：

```powershell
pdfinfo docs\FinDSL_Forge_中文操作手册.pdf
pdftoppm -png -f 1 -l 3 -r 120 docs\FinDSL_Forge_中文操作手册.pdf reports\operation_manual_pdf_pages\page
```

如果抽样页面为空白、乱码或表格严重错位，应重新导出，并检查 Markdown 中是否存在过宽表格、异常字符或未闭合代码块。

## 第12章 使用注意事项

第一，性能数字必须带上实验边界。36.24x 来自当前 5M Doris、120 日成交量滚动 SUM、prefix 热点路径，不代表所有查询都有同等加速。

第二，真实行情小样本用于业务可信度演示，不用于性能证明。性能证明应使用 Doris cluster evidence。

第三，新增函数或指标后必须补齐 semantic、SQL、reference 和 official suite 证据。只让样例能编译，不等于赛题要求已经满足。

第四，不要把 LLM 输出当作 SQL 执行依据。所有候选都必须回到 DSL 编译链路。

第五，提交前不要临时大改演示路径。若必须修改，应重新运行 pytest、readiness、export artifacts，并同步 README、手册、PPT 和讲稿中的关键数字。

第六，文档与代码应一起维护。操作手册不是最后临时附上的说明，而是项目交付的一部分。凡是启动命令、端口、证据数字、目录结构或演示路径发生变化，都应同步更新 Markdown、DOCX 和 PDF。

第七，现场演示应准备离线兜底路径。即使外网、provider 或 Docker 镜像临时不可用，也应能展示本地 Web Demo、离线 LLM 候选验证、官方正负例、readiness 快照和已采集 Doris evidence。竞赛现场稳定性比临时联网能力更重要。

## 第13章 深度使用场景说明

本章补充说明 FinDSL Forge 在不同使用场景下应当如何被理解和使用。前面的章节已经给出了命令和步骤，但真实项目交付不能只停留在“输入一条命令得到一条结果”。评审、答辩、开发、维护和后续扩展面对的是不同问题：评审想知道系统是否可信，答辩人员想知道现场怎么讲，开发者想知道出错后如何定位，维护人员想知道后续如何扩展而不破坏现有能力。把这些场景讲清楚，文档才真正像一份可用的软件操作手册。

### 13.1 评审验收场景

在评审验收场景中，操作者不应把系统介绍成一个简单的“自然语言转 SQL 工具”。这个说法过于粗略，也容易让评委误以为项目只是套了一层大模型接口。更准确的表达是：FinDSL Forge 是一套面向金融选股 DSL 的确定性编译与验证系统，中文输入只是入口之一，核心能力在于把受限 DSL 稳定编译为 Doris SQL，并用多条证据链证明语义正确和性能有效。

评审人员首先会关心系统能否覆盖赛题中的关键语义。这里的关键语义包括 `then` 的阶段化筛选与排名、`CONS/EXIST` 的连续和存在条件、窗口函数、收益率计算、日期区间、跨市场布尔组合、配置化指标以及 prefix-sum 长窗口优化。操作人员在展示时不必把所有语法都逐项展开，但应当用一两个代表性案例说明系统不是只支持单表简单过滤，而是能够处理多个语义组合。

评审人员还会关心结果是否可信。此时不要只展示 SQL 字符串，因为 SQL 字符串本身不能证明语义正确。更好的展示方式是先展示 DSL，再展示 AST，随后展示 Doris SQL 和 Explain，最后展示 SQL/reference equivalence 或 readiness 报告。这样可以让评审看到系统有完整的输入、解析、编译、优化和验证过程。对于金融科技类项目，这种可解释链路比单纯展示“运行成功”更有说服力。

如果评审追问性能，应直接说明性能证据来自 Doris cluster evidence，而不是来自本地 SQLite timing。SQLite 的存在价值是快速语义回归，Doris evidence 才是长窗口性能证明。当前项目保留 5,000,000 行 Doris 规模证据，说明 120 日成交量滚动 SUM 在 prefix 热点路径上达到 36.24x 加速。这个数字应当带着实验边界一起讲，避免让人误以为所有查询都固定加速 36 倍。

评审验收时还可能关注“新指标是否真的可以配置化扩展”。答复时应说明：普通指标可以通过 `configs/indicators.json` 声明表、列、类型和 prefix-sum 元信息，项目中也有 config-only indicator extension 的防守证据；但如果新增的是全新函数或全新语义类别，仍然需要补充语义分析、SQL 生成和 reference evaluator。这样的回答既体现配置化能力，也不会夸大系统边界。

### 13.2 答辩演示场景

答辩演示最重要的是节奏。很多项目在功能上并不弱，但现场讲解时把命令、代码、截图和报告混在一起，听众很快失去主线。FinDSL Forge 的演示建议围绕“用户表达、编译生成、优化解释、结果验证、异常处理、性能证据”六个动作展开。每个动作都对应一个明确的得分点，避免把演示变成漫无目的的页面切换。

第一步适合从中文需求开始。可以输入“筛选A股连续三天主力净流入为正并按换手率排名前一百”，让系统生成候选 DSL。此时要强调，中文输入只是帮助用户降低表达门槛，系统并没有让大模型直接访问数据库。候选 DSL 仍然进入确定性编译器，必须通过语义校验和 reference 验证。

第二步展示 DSL 和 AST。这里可以说明，AST 是系统理解 DSL 的结构化结果，它让后续语义检查和 SQL 生成有稳定基础。对于评委来说，看到 AST 的意义在于确认系统不是简单字符串替换，而是有真正的语法结构处理。

第三步展示 SQL 和 Explain。SQL 说明系统最终面向 Doris 执行，Explain 则说明编译器为什么应用某些规则，例如日期下推、滚动窗口特征层、prefix-sum rewrite、Doris SQL validation 等。讲解时不要只念规则名，而要用自然语言解释：“这个规则的作用是把窗口函数从 WHERE 中移出去，避免生成 Doris 不友好的 SQL”；或者“这个规则把长窗口 SUM 改写为前缀表访问，减少重复窗口扫描”。

第四步展示结果验证。Rows 或 Evidence 区域能证明 SQL 输出与参考语义一致。这里可以强调 reference evaluator 是独立路径，不是 SQL generator 自己验证自己。这样能回应评审对正确性的关切。

第五步展示负例。推荐使用未知指标 `clos` 或直接 SQL 候选，让系统返回诊断和修复建议。负例展示的目的不是证明用户会犯错，而是证明系统面对错误输入时不会悄悄生成危险 SQL。金融系统尤其需要这种失败边界。

第六步展示 readiness 和 Doris evidence。此时可以打开 `submission_artifacts/evidence_snapshots/submission_readiness.md`，展示 `184 passed`、正例 `37/37`、负例 `37/37`、Doris 证据 PASS 和 warning count 0。最后用一句话收束：“前面演示的是交互路径，这里展示的是可复核证据。”这样的收尾比单独展示截图更有力量。

### 13.3 开发调试场景

开发调试时，最重要的原则是先确定问题所在层级，再动手修复。FinDSL Forge 的链路较长，包含 lexer、parser、semantic analyzer、SQL generator、validator、reference evaluator、SQLite executor、Doris evidence 和 Web Demo。如果一看到失败就直接改 SQL 生成，很容易修掉表面现象，却破坏其他语义。

当 DSL 无法解析时，先看 lexer 和 parser。典型问题包括非法字符、括号不匹配、字符串引号错误、命名参数顺序错误等。此类问题通常应返回 parse 或 lex diagnostic，而不应进入 SQL 生成阶段。如果错误输入仍然生成 SQL，说明前置校验失效。

当 DSL 能解析但语义不合法时，先看 semantic analyzer。典型问题包括 `filter` 条件不是布尔类型、窗口参数不是正整数字面量、`rank` 的 top/bottom 与排序方向不匹配、`RET` 内嵌窗口函数、裸字段名绕过 `indicator()` 等。语义层的职责是把不合法但语法上能写出来的表达挡住。

当语义合法但 SQL/reference 不一致时，应把问题视为正确性问题，而不是性能问题。可以先运行 `verify-sql`，观察 missing keys 和 extra keys，再查看生成 SQL 的窗口边界、日期下推、join 类型和 rank 排序。尤其是涉及辅助表时，要确认系统仍以 `daily_quote` 为股票日期骨架，避免因 money_flow 缺失行导致筛选宇宙变化。

当 prefix-sum 路径出问题时，要同时检查配置和数据。配置中必须有 `supports_prefix_sum`、`prefix_table` 和 `prefix_column`；前缀表中必须有与基础表一致的 `ts_code`、`trade_date`、`row_no`；对于热点窗口列，例如 `volume_sum_120`，还要确认 schema 和 SQL generator 使用的是同一列名。只看 SQL 字符串不足以定位这类问题。

当 Web Demo 异常时，应分清前端展示问题和后端编译问题。若 CLI 正常但 Web Demo 不正常，优先检查 Demo API；若 CLI 和 Demo 都失败，问题多半在编译器或数据层。调试时建议先用最小命令复现，不要一开始就在浏览器里反复点击。

### 13.4 维护交接场景

维护交接的重点不是让下一位同学读完所有代码，而是让他知道哪些文件是主线、哪些命令是验收入口、哪些报告能说明系统状态。项目交接时，建议先打开 README，再打开本操作手册，然后查看 `docs/architecture.md` 和 `docs/doris_runbook.md`。这样可以从使用、架构和性能证据三个层次建立整体认识。

交接时应明确哪些文件属于源文件，哪些文件属于生成物。`src/findsl`、`configs`、`tests`、`data/samples`、`docs` 和 `scripts` 是维护重点；`reports` 多数是本地生成结果；`submission_artifacts/evidence_snapshots` 是提交用证据快照。维护者需要知道，修改源文件后要重新生成报告和快照，不能只改代码不改证据。

如果交接版本已经推送到 GitHub，应记录最新 commit hash。如果还生成了 bundle，应记录 bundle 路径和验证结果。远端仓库和离线 bundle 各有价值：GitHub 方便协作，bundle 适合在网络不可用或远端权限变化时恢复。竞赛后期尤其需要保留 bundle，因为最终材料往往在短时间内多次调整。

交接人员还应检查文档和证据数字是否一致。比如本操作手册写 `184 passed` 和 `37/37`，就应与 latest readiness snapshot 一致。若后续测试数量变化，应同步更新本文档、综合指南、PPT 和讲稿。数字不一致会让评审怀疑材料是拼凑的。

### 13.5 课程或项目验收场景

如果 FinDSL Forge 被用于课程设计、毕业设计或项目验收，文档表达应更注重“可复现”和“可解释”。验收人员未必熟悉 Doris 或金融 DSL，因此不能只说系统实现了 prefix-sum 优化，而要解释为什么长窗口 SUM 在行情选股中常见，为什么普通窗口扫描代价高，为什么前缀表能够把重复计算转化为查找和差分。

课程验收通常还会关注工作量和工程完整度。此时可以展示模块划分：lexer/parser 负责语言入口，semantic 负责类型与规则约束，sqlgen 负责 Doris SQL，reference 负责独立语义，executor 负责本地执行，doris_evidence 负责真实数据库证据，demo 负责交互展示，readiness 负责总验收。这个模块划分说明项目不是单脚本原型，而是有工程边界。

项目验收还应说明为什么保留负例测试。很多初学项目只验证正例能跑通，实际系统却经常失败在错误输入上。FinDSL Forge 把未知指标、非法窗口、非法 rank、直接 SQL、裸字段绕过等负例纳入 official suite，说明系统对错误输入有预期行为。

如果验收要求提供安装部署说明，本操作手册可以直接作为附件。若验收要求提供设计说明，应同时提交 `docs/FinDSL_Forge_中文综合操作指南.md` 或其 DOCX 版本。前者偏操作，后者偏项目背景、架构、算法和答辩材料，二者互补。

## 第14章 主要功能模块详解

本章从使用者角度解释各功能模块的作用。它不替代源码注释，也不展开每个函数的实现细节，而是说明每个模块在系统中的位置、使用时应关注什么、出现问题时应如何判断。

### 14.1 DSL 编译模块

DSL 编译模块是系统核心。它的职责是把用户输入的 FinDSL 表达式转换为结构化 AST，并进一步生成 Doris SQL。使用者看到的是一条命令或一个页面按钮，内部实际经历了词法分析、语法解析、语义校验和 SQL 生成。这个过程之所以要分层，是为了让每类错误在合适的位置被发现。

词法分析负责识别字符串、数字、标识符、比较符和布尔运算符。语法解析负责确认括号、函数调用、参数顺序和表达式优先级。语义校验负责判断表达式是否有业务意义，例如 `filter` 必须接收布尔条件，窗口大小必须是正整数，`rank` 的方向和 top/bottom 不能冲突。SQL 生成则在前面都合法的基础上输出 Doris SQL。

使用编译模块时，建议先用简单 DSL 验证基础环境，再逐步增加窗口、日期和 ranking 条件。比如先运行 `filter(indicator("close") > 10)`，再运行 `filter(market("A") & indicator("close") > 10)`，最后运行包含 `CONS`、`MA` 或 `SUM` 的复杂表达。这样可以更快定位问题是基础环境、指标配置还是高级语义造成的。

编译模块的预期结果不仅是一条 SQL，还应包括 AST、trace 和 explain。AST 说明系统如何理解表达式，trace 说明编译过程中的人类可读动作，explain 说明机器可读优化规则。答辩或验收时，不要只复制 SQL，应尽量展示这三类辅助信息。

### 14.2 语义验证模块

语义验证模块的价值在于阻止“看起来像 DSL，但业务上不成立”的表达进入 SQL 生成。金融选股系统如果缺少这一层，很容易把错误条件翻译成看似可执行的 SQL，最终产生静默错误。静默错误比显式报错更危险，因为用户可能相信错误结果。

例如，`filter(indicator("close"))` 在语法上是一个函数调用，但 `filter` 需要布尔条件，单独的数值指标并不能作为筛选条件。系统应提示用户把数值表达式写成比较形式，例如 `filter(indicator("close") > 10)`。这种提示看似细小，却能显著提升系统可用性。

又如，`rank(indicator("close"), asc, top=10)` 语义上存在方向矛盾。`asc` 表示低值在前，若用户想取低价前 10，应使用 `bottom=10`；若想取高价前 10，应使用 `desc, top=10`。系统在语义层拦截这类问题，能避免排名结果与用户意图相反。

语义验证模块还承担安全边界职责。裸字段名、静态除零、非法市场参数、非法日期范围等都应在 SQL 生成前失败。维护者扩展新语法时，应同步思考新语法有哪些非法形态，并把这些非法形态写入 negative cases。

### 14.3 SQL 生成与 Doris 适配模块

SQL 生成模块把合法 DSL 转换为 Doris SQL。Doris 虽然兼容 MySQL 协议，但并不意味着任意 SQL 写法都适合 Doris 执行。系统需要考虑窗口函数位置、CTE 阶段、日期裁剪、辅助表 join、前缀表路径和 SQL shape 安全检查。

对于窗口函数，系统会把 `MA`、`MAX`、`MIN`、`SUM`、`RET` 等特征放入中间层，再在外层 WHERE 中过滤。这是因为许多数据库不允许直接在 WHERE 中使用窗口函数。通过 feature layer，SQL 既保持语义清晰，也更接近 Doris 可执行形态。

对于 `then`，系统会生成 staged CTE pipeline。这样可以表达“先筛选，再排名”或“先排名，再继续过滤”的业务语义。若直接把多个条件揉成一个 WHERE，很容易改变阶段顺序，尤其在 rank 场景中会导致结果不同。

对于辅助表，系统采用以 `daily_quote` 为基础的左连接策略。这样做是为了保持股票日期宇宙稳定，避免资金流表或其他辅助表缺失数据时把基础行情行过滤掉。对于金融数据来说，缺失辅助指标与股票不存在不是同一件事，SQL 生成必须保留这个区别。

SQL 生成完成后，Doris SQL validator 会检查单语句形态、表引用、窗口位置和字面量转义等内容。该检查不能替代数据库执行，但能在 SQL 进入 Doris 前挡住明显危险或不符合约束的输出。

### 14.4 Reference Evaluator 与等价验证模块

Reference evaluator 是项目正确性证据的核心之一。它用 Pandas 按 DSL 语义直接解释样本数据，形成一条独立于 SQL generator 的参考路径。然后系统把编译生成的 SQL 在 SQLite 或 Doris 上执行，再比较两边的结果集。

这条路径的意义在于避免“编译器自己证明自己正确”。如果只有 SQL generator 输出 SQL，再由同一个逻辑判断 SQL 是否正确，证据说服力很弱。Reference evaluator 采用不同实现方式，能更容易暴露窗口边界、rank 顺序、日期裁剪和 join 语义上的偏差。

使用等价验证时，应关注三个结果：`passed`、missing keys 和 extra keys。`passed=true` 说明结果一致；missing keys 表示 SQL 少返回了 reference 中应有的记录；extra keys 表示 SQL 多返回了 reference 中没有的记录。两类差异的定位方向不同，前者可能是过滤过严或 join 丢行，后者可能是过滤过松或窗口边界错误。

维护者新增语法后，必须同步更新 reference evaluator。否则新语法即使能生成 SQL，也无法纳入等价验证。对于竞赛项目来说，不能被 reference 验证的新功能不应作为核心完成项宣传。

### 14.5 NL2DSL 与 LLM 安全模块

NL2DSL 模块的作用是把中文自然语言请求转成候选 FinDSL，而不是把中文直接转成 SQL。这个边界非常重要。金融数据查询需要稳定、可解释、可审计的执行路径，直接让模型生成 SQL 会带来字段幻觉、口径漂移、注入风险和不可复现问题。

项目中的确定性中文模板适合演示常见官方风格场景。它能识别低价排名、换手率百分比、B 股均量、日期窗口、主力净流出、收益率和 prefix-sum 相关请求。模板输出的仍然是 DSL，随后进入完整编译与验证链路。

LLM 候选验证模块用于处理外部模型返回内容。它会提取候选 DSL，拒绝直接 SQL，编译合法候选，并在开启验证时要求 SQL/reference 一致。这个模块的价值不是展示模型有多强，而是展示系统如何使用模型但不被模型控制。

如果现场没有 provider key 或网络不稳定，不影响核心演示。可以使用 `data/samples/llm_candidate_response.json` 做离线安全验证，证明合法候选会被接受，拼错指标会返回诊断，直接 SQL 会被拒绝。这样的离线路径更适合正式答辩，因为它可复现，不依赖现场网络。

### 14.6 Readiness 总验收模块

Readiness 是项目提交前最重要的总开关。它把分散的测试和证据整合到一个报告中，包括 pytest、编译评估、SQL 等价验证、prefix benchmark、Demo API smoke、NL2DSL smoke、LLM safety、diagnostics、Doris SQL validation、真实行情样本、official suite、defense package、Doris asset integrity、Doris cluster evidence 和 Git cleanliness。

使用 readiness 时，不能只看命令是否退出成功，还要阅读 Decision Summary 和 Gate Matrix。`Blocking gates passed: True` 说明必需门禁通过；`Warning count: 0` 说明当前没有提交风险提示；Git rollback cleanliness PASS 说明工作区干净。若 warning count 不为 0，要根据 warning 内容判断能否接受。

Readiness 的价值在于防止“局部成功”。比如 pytest 通过但 Doris evidence 缺失，系统仍然不适合声称性能目标完成；Demo 能打开但 official suite 失败，也不能说明赛题覆盖完整；Doris evidence 通过但 Git 工作区脏，则说明证据和代码版本可能不一致。

最终提交前，应以 readiness 快照作为证据基准。导出提交材料后，如果又修改了代码或文档，应重新运行 readiness 并重新导出 artifacts。不要把旧报告和新代码混在一起提交。

## 第15章 操作过程中的结果判断

很多操作手册只写“执行某命令”，却没有说明执行后应该看到什么、如何判断结果好坏。本章专门说明常见命令和页面动作的结果判断方法，帮助操作者在没有开发者陪同的情况下确认系统状态。

### 15.1 编译命令的结果判断

执行 `compile` 后，最基本的成功标志是命令没有异常退出，并输出 SQL。更完整的判断还包括：AST 中函数名和参数与输入 DSL 一致；SQL 中表名来自配置而不是用户随意拼接；Explain 中出现 `DORIS_SQL_VALIDATION`；编译耗时明显低于赛题要求的 50ms P95 目标。

如果输入包含窗口函数，例如 `MAX(indicator("close"), 250)`，SQL 中应出现 `OVER (PARTITION BY ts_code ORDER BY trade_date ...)`。如果输入包含 `SUM(indicator("volume"), 120)` 且 prefix-sum 开启，SQL 中应引用 `dwd_stock_daily_quote_prefix` 或热点窗口列。若这些片段缺失，需要检查指标是否声明支持 prefix-sum，以及编译器是否在 staged relation 中禁用了该优化。

如果输入包含日期区间，SQL 应出现 `trade_date` 条件。对于非窗口条件，可以完整下推日期范围；对于窗口条件，系统可能只安全地下推上界，以避免破坏历史窗口。看到这种差异时不要误以为系统漏掉了下界，它可能是为了保持窗口语义正确。

### 15.2 等价验证的结果判断

执行 `verify-sql` 后，应重点看 `passed`、`sql_row_count`、`reference_row_count`、`missing_keys` 和 `extra_keys`。只有 `passed=true` 且 missing/extra 为空，才能说明当前样本上的 SQL 与参考语义一致。

如果 SQL 行数和 reference 行数相同，但 keys 不一致，说明结果数量碰巧一样，语义仍然不一致。此时要查看具体缺失和多出的 `(ts_code, trade_date)`，根据日期、股票代码和条件类型定位问题。不要只看行数一致就认为通过。

如果结果差异集中在某个股票的早期日期，常见原因是窗口边界、`min_periods` 或 lag 处理不一致。如果差异集中在辅助指标缺失日期，常见原因是 join 类型或 prefix table 构建骨架不一致。如果差异集中在排名结果，常见原因是排序方向、空值过滤或 tie-breaker 不一致。

### 15.3 Official Suite 的结果判断

Official suite 的正例不仅要求编译通过，还要求 SQL fragment、trace fragment、explain rule 和 reference equivalence 全部满足。也就是说，它检查的是“系统是否按预期方式实现”，而不是只看最终能不能返回结果。

正例失败时，要看 missing evidence 是哪一类。如果 missing SQL fragment，说明生成 SQL 形态不符合预期；如果 missing trace fragment，说明编译路径说明发生变化；如果 missing explain rule，说明可解释优化证据缺失；如果 equivalence 失败，说明语义结果不一致。

负例失败时，要看 expected code 和 actual code。如果非法 DSL 意外编译成功，这是严重问题；如果返回了错误但诊断码不稳定，说明用户或评审无法根据错误类型做修复；如果没有 suggestion，则错误提示不够可操作。

### 15.4 Doris Evidence 的结果判断

Doris evidence 的判断比本地测试更严格。首先 baseline 和 optimized 都必须成功执行；其次两者 row count 必须一致；再次 baseline plan 应包含窗口路径，optimized plan 应包含 prefix table；最后 measured speedup 必须达到阈值。缺少任何一项，都不应把该报告作为最终性能证明。

如果 optimized 比 baseline 快，但行数不一致，这不是成功优化，而是错误优化。正确性优先于性能。只有在结果一致的基础上，性能比较才有意义。

如果 optimized plan 没有出现 prefix table，说明优化路径可能没有真正生效。此时即使耗时较短，也不能说明 prefix-sum 设计有效。需要回到 SQL 和 Explain 查看 `PREFIX_SUM` rule 是否 applied，以及指标配置是否正确。

如果 speedup 未达 10x，但 plan shape 正确且行数一致，可能是数据量不够、缓存影响、Doris 资源不足或物理布局不理想。可以增加数据规模、关闭 SQL cache、检查分区与 colocate 状态，或重新采集多轮迭代数据。

### 15.5 Web Demo 的结果判断

Web Demo 成功并不只是页面能打开。更准确的判断是：输入后能生成候选 DSL，候选 DSL 能被验证，SQL 区域能展示 Doris SQL，AST 区域能展示结构，Explain 区域能展示规则，Rows 或 Evidence 区域能展示验证结果，Diagnostic 区域能处理负例。

如果页面能打开但请求无响应，可能是后端 API 异常或浏览器请求失败。应查看 PowerShell 启动窗口或日志文件。若只有某个 preset 失败，应把该 preset 对应 DSL 拿到 CLI 中单独复现。

如果页面显示结果但数字与 readiness 不一致，说明截图或报告可能来自不同版本。答辩前应刷新截图或调整讲稿，避免现场材料互相矛盾。

## 第16章 面向非开发者的操作说明

本章面向不熟悉 Python、Doris 或编译器的读者，用更接近中文说明书的方式解释如何使用系统。它的目标不是降低技术准确性，而是减少读者理解门槛。

### 16.1 如果只想看系统能做什么

如果读者只是想快速了解系统能力，建议先打开 Web Demo，而不是直接阅读源码。Web Demo 能把项目能力集中展示出来：输入中文需求，系统给出 DSL，继续生成 SQL，展示 AST 和 Explain，最后给出验证结果。这个过程比直接看代码更直观。

打开页面后，可以先使用默认请求，不要急着修改。默认请求经过项目验证，能稳定展示完整链路。等理解页面结构后，再尝试低价排名、换手率百分比、日期窗口和负例诊断。这样更容易理解每个区域的含义。

如果只看一个技术亮点，建议看 prefix-sum 示例。它能说明系统不只是翻译 SQL，还会根据长窗口查询选择优化路径。Explain 中的 `PREFIX_SUM` 和 SQL 中的 prefix table 是关键证据。

### 16.2 如果只想确认项目是否可提交

如果读者的目标是确认项目是否可提交，不需要逐个运行所有命令，首先应查看 `submission_artifacts/evidence_snapshots/submission_readiness.md`。这份快照是提交用证据，记录了最近一次总验收结果。

确认时重点看 Decision Summary：`Blocking gates passed` 是否为 True，`Warning count` 是否为 0。然后看 Gate Matrix：pytest、official suite、defense package、Doris asset integrity、Doris-scale performance proof 和 Git rollback cleanliness 是否通过。最后看 Competition Metrics，确认正例、负例、真实行情样本、编译 P95 和 Doris 证据数字。

如果这些内容都正常，再检查 Git 状态和 bundle。代码、报告和备份同时齐全，才能说项目具备可提交状态。若仅有报告但本地工作区存在未提交修改，需要先提交或说明原因。

### 16.3 如果只想准备答辩

准备答辩时，不建议从头背诵操作手册。更有效的方法是准备一条主线：问题是什么，方案怎么做，系统如何演示，证据在哪里。每句话都应能对应到 Demo 页面或报告文件。

可以把答辩讲解分成三层。第一层讲业务痛点：金融选股表达复杂，直接写 SQL 容易错，长窗口查询性能压力大。第二层讲系统方案：受限 DSL、确定性编译器、Doris SQL、reference equivalence、prefix-sum 优化。第三层讲证据：官方正负例、pytest、Doris evidence、readiness、截图和视频。

答辩人应提前练习负例说明。很多现场追问会围绕系统边界展开，例如“如果模型生成 SQL 怎么办”“如果指标写错怎么办”“如果日期窗口导致结果不准怎么办”。这些问题都可以用诊断模块、LLM safety loop 和 reference equivalence 回答。

### 16.4 如果只想后续继续开发

后续开发应先熟悉测试，而不是先改功能。测试能告诉维护者系统当前有哪些承诺。新增能力时，维护者应先写或修改官方风格用例，再修改编译器和 reference evaluator，最后跑 readiness。这种方式能减少回归风险。

如果要新增普通指标，优先从 `configs/indicators.json` 入手。新增后运行 config extension 和 official suite。如果要新增函数，先判断函数返回的是 numeric、boolean 还是 relation，再设计语义约束、SQL 生成方式和 reference 解释方式。函数扩展通常比指标扩展复杂，不应简单等同。

如果要增强 Web Demo，应确保 UI 展示的字段仍来自后端稳定 JSON，不要在前端重新解释 DSL 或 SQL。Demo 的职责是展示编译器结果，不应把业务逻辑复制到浏览器端。

### 16.5 如果遇到问题不知道从哪里看

遇到问题时，先不要同时修改多个文件。可以按以下顺序定位：命令是否能运行，Python 环境是否正确，DSL 是否能 compile，SQL/reference 是否一致，official suite 是否通过，readiness 中哪个 gate 失败。这个顺序从小到大，能逐步缩小范围。

如果错误发生在命令行，优先保存完整错误输出。如果错误发生在 Web Demo，先用同一 DSL 在 CLI 中复现。如果错误发生在 Doris，先确认本地 SQLite 等价验证是否通过，再看 Doris schema 和数据加载。如果 SQLite 也失败，说明问题不在 Doris，而在编译或语义层。

维护者应养成记录问题和修复过程的习惯。尤其是 Doris 相关问题，经常与环境、数据量、容器状态和网络有关。记录当时的命令、环境变量、报告文件和错误信息，能帮助后续团队成员少走弯路。

## 第17章 完整操作案例说明

本章用更完整的案例说明系统如何从用户需求走到可验证结果。前面章节已经给出分散命令，本章把这些命令放回真实操作语境中，让读者理解每一步为什么要做、做完以后应该看到什么、如果结果不符合预期应该如何继续处理。

### 17.1 案例一：A 股连续资金流入后按换手率排名

这个案例适合用于第一次演示，因为它同时包含市场约束、连续条件和排名逻辑，能较好地体现系统不是简单单条件过滤。业务语言可以描述为：“筛选 A 股连续三天主力净流入为正，并按换手率排名前一百”。在真实券商或行情分析场景中，这类需求很常见：用户希望先找出资金行为持续改善的股票，再从中按活跃度排序。

在 Web Demo 中输入该中文需求后，系统会生成类似下面的 DSL：

```text
then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))
```

这条 DSL 有两个阶段。第一阶段是 `filter`，其中 `market("A")` 限定 A 股，`CONS(..., 3)` 表示连续三天满足主力净流入大于 0。第二阶段是 `rank`，表示在筛选后的股票集合中，按换手率降序排名并取前 100。这里的 `then` 非常关键，它保证“先筛选再排名”的顺序不会被 SQL 生成过程改变。

使用命令行验证时，可以执行：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli verify-sql 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))' --data-dir data/samples --json
```

如果返回结果中 `passed` 为 `true`，说明 SQL 输出与参考语义一致。展示时可以进一步说明：`CONS` 会被编译成滚动窗口特征，`rank` 会被编译成 `ROW_NUMBER()` 窗口排名，`then` 会被编译成 CTE 阶段。这样一条案例就能覆盖多个赛题核心要求。

如果该案例失败，常见问题包括 money_flow 样本缺失、辅助表 join 逻辑异常、`CONS` 窗口边界变化或 rank 规则变动。排查时应先运行 official suite，因为该案例属于官方风格正例的一部分；如果 official suite 中只有这个案例失败，就集中检查滚动布尔和 staged rank。

### 17.2 案例二：日期区间内滚动成交量累计筛选

这个案例适合展示 prefix-sum 优化。业务语言可以描述为：“在指定日期区间内，筛选近三日成交量累计大于 300 的记录”。对应 DSL 可以写成：

```text
filter(date_between("2026-01-02", "2026-01-04") & SUM(indicator("volume"), 3) > 300)
```

这条 DSL 同时包含日期区间和滚动 SUM。普通 SQL 可以用窗口函数计算滚动成交量，但在长周期、大规模行情数据上，重复窗口扫描会带来明显性能压力。FinDSL Forge 对配置了 prefix-sum 的指标会尝试生成前缀表访问路径，用当前前缀值减去窗口前的前缀值，得到同样的滚动和。

在本地样本中，可以先运行：

```powershell
python -m findsl.cli verify-sql 'filter(date_between("2026-01-02", "2026-01-04") & SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json
```

验证通过后，再查看 compile 输出中的 SQL 是否包含 `dwd_stock_daily_quote_prefix`。如果包含，说明优化路径已经进入 SQL。对于短窗口样本，这主要是形态验证；真正的性能结论仍要看 Doris evidence。

答辩时可以把这个案例讲成两层：第一层证明系统能正确处理日期区间和滚动窗口；第二层证明系统能把长窗口滚动 SUM 路由到 prefix-sum 路径。不要只说“用了前缀和”，而要解释为什么前缀和适合滚动 SUM：因为窗口和可以通过两个累计值相减得到，避免每个结果行重复扫描窗口范围。

如果结果不一致，应重点检查日期裁剪。对于窗口查询，盲目下推完整日期区间可能会丢失窗口所需的历史行。项目中区分 full range、upper bound 和 prefix full range，正是为了避免这个问题。排查时应查看 Explain 中的 `DATE_RANGE_WINDOW_PRUNING` 或 `DATE_RANGE_PREFIX_PRUNING`。

### 17.3 案例三：收益率筛选

收益率筛选适合展示 `RET` 函数。业务语言可以描述为：“筛选近 2 日收盘价涨幅超过 5% 的股票记录”。对应 DSL 为：

```text
filter(RET(indicator("close"), 2) > 0.05)
```

`RET` 的语义是当前值相对 N 日前值的收益率。SQL 生成时会使用 `LAG` 获取 N 日前的收盘价，并通过 `NULLIF` 避免除零问题。这个设计不仅能生成结果，也体现了金融指标计算中的边界处理。

运行验证命令：

```powershell
python -m findsl.cli verify-sql 'filter(RET(indicator("close"), 2) > 0.05)' --data-dir data/samples --json
```

预期结果应为通过。展示 SQL 时，应能看到 `LAG(close, 2) OVER` 和 `NULLIF`。如果 SQL 中没有这些片段，说明收益率函数没有走预期 rewrite 路径。

收益率案例的讲解重点在于“不是简单价格相减”。收益率要考虑比例关系，要考虑前值为零的情况，也要按股票代码和交易日期排序。系统把这些规则封装在 `RET` 中，可以避免用户每次手写复杂 SQL。

如果该案例在真实行情样本中运行，建议使用 date_between 限制日期范围，避免展示结果过多。真实行情样本的用途是说明系统能处理实际日期和股票代码，不是为了证明收益率策略有效。

### 17.4 案例四：跨市场布尔异或

跨市场布尔异或是最新补齐的能力，适合展示系统对赛题原文 `|&^` 的覆盖。示例 DSL 为：

```text
filter(market("A") ^ indicator("close") > 10)
```

这条表达式表示“市场为 A”和“收盘价大于 10”两个条件中恰好一个为真。它不是常规的 AND 或 OR，而是异或逻辑。SQL 生成时，系统会把左右布尔条件分别转换为 0/1，再用 `<>` 判断二者是否不同。这样可以避免 SQL 三值逻辑中的空值干扰。

运行编译命令：

```powershell
python -m findsl.cli compile 'filter(market("A") ^ indicator("close") > 10)' --json
```

预期 SQL 中应出现：

```text
CASE WHEN market = 'A' THEN 1 ELSE 0 END
CASE WHEN close > 10 THEN 1 ELSE 0 END
<>
```

该案例的价值不在于策略本身多常用，而在于证明系统对赛题提出的复杂布尔组合有完整链路支持。它覆盖 lexer、parser、semantic、SQL generator、reference evaluator 和 official suite。答辩中如果评委问到 `^`，可以直接展示这个案例。

### 17.5 案例五：未知指标诊断

未知指标诊断适合展示系统的错误恢复能力。输入：

```text
filter(indicator("clos") > 10)
```

这里 `clos` 很可能是用户把 `close` 写错了。系统应返回 `UNKNOWN_INDICATOR` 相关诊断，并给出接近 `indicator("close")` 的修复建议。这个案例说明系统不仅能处理正确输入，也能帮助用户把错误输入改回合法表达。

命令行验证：

```powershell
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json
```

展示时可以解释，错误诊断不是简单捕获异常，而是把异常转换为稳定错误码和可操作建议。对于真实业务系统，这类体验很重要，因为用户不一定熟悉所有指标名称。

如果诊断没有给出建议，只显示原始异常，说明 diagnostics 层出现退化。维护者应优先修复诊断，而不是让用户去读 Python stack trace。

### 17.6 案例六：直接 SQL 候选拒绝

该案例适合说明 AI 安全边界。LLM 或用户可能返回一段 SQL，例如 `SELECT * FROM ...`。FinDSL Forge 不接受这类内容作为可执行候选，而是返回 `UNSAFE_DIRECT_SQL`。这是设计选择，不是功能缺失。

可以使用内置响应文件验证：

```powershell
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --json
```

预期结果中，一个合法 DSL 被接受，一个拼写错误候选被诊断，一个直接 SQL 被拒绝。答辩时应强调，系统允许 AI 帮助用户表达意图，但不允许 AI 绕过编译器和 SQL validator。这个边界符合金融数据系统对可控性和审计性的要求。

如果评委追问为什么不直接让模型生成 SQL，可以回答：直接 SQL 难以保证字段口径、权限边界、窗口语义和性能路径，且输出不稳定；受限 DSL 虽然表达空间更小，但更适合金融场景的确定性执行。

## 第18章 讲解口径与文档表达建议

本章帮助答辩人员把技术内容转化为自然中文表达。很多技术项目的问题不是没做出来，而是讲解时过度使用口号或堆砌术语。FinDSL Forge 的讲解应尽量使用清楚的中文句子，把“为什么做、怎么做、怎么证明”讲成连续逻辑。

### 18.1 项目一句话介绍

可以这样介绍项目：

FinDSL Forge 是一套把金融行情选股 DSL 自动编译为 Apache Doris SQL 的系统。它用确定性编译器保证语义可控，用 reference evaluator 和 SQL 执行结果证明正确性，用 prefix-sum 优化长窗口查询性能，并用 readiness 报告把测试、性能和提交证据统一起来。

这句话包含四层意思：系统对象是金融选股 DSL，目标执行环境是 Doris SQL，核心方法是确定性编译和验证，竞争亮点是 prefix-sum 性能证据和 readiness 交付链。讲解时可以先说这句话，再展开细节。

不建议把项目说成“基于大模型的智能选股系统”。这个说法容易让评委把注意力放到模型效果和投资收益上，而本赛题真正关注的是 DSL 到 Doris SQL 的编译、优化和工程落地。项目可以使用 AI 辅助入口，但核心不是预测股票，也不是生成投资建议。

### 18.2 赛题痛点表达

赛题痛点可以从两个角度讲。业务角度是：分析师的选股条件越来越复杂，经常包含连续、存在、排名、收益率和日期区间，直接写 SQL 成本高且容易错。工程角度是：如果每个新指标都要改 Java 后端或手写 SQL 模板，维护成本高，业务规则也容易散落在代码里。

进一步讲，金融数据的错误不一定会报错。比如日期下界下推错误可能让滚动均线少看历史数据，辅助表 inner join 可能悄悄丢掉缺失资金流的股票日期，rank 方向写反可能让“低价股”变成“高价股”。这些错误看起来都能返回结果，但结果口径已经错了。

FinDSL Forge 的价值就是把这些隐性风险显式化。通过 DSL 限定表达，通过 semantic analyzer 拦截非法语义，通过 reference equivalence 检查结果，通过 Explain 记录优化路径，通过 readiness 统一证据。这样讲比只说“降低开发成本”更具体。

### 18.3 技术方案表达

技术方案可以按四层讲：语言层、编译层、执行层、证据层。语言层定义 FinDSL，让用户用受控表达描述选股逻辑；编译层把 DSL 变成 AST，并生成 Doris SQL；执行层使用 SQLite、本地样本和 Doris 集群验证结果；证据层用 official suite、Doris evidence 和 readiness 把结果固化。

讲语言层时，要强调受限不是缺点，而是金融系统需要的安全边界。开放 SQL 表达能力强，但也意味着用户可以绕过规则、引用未知表、写出性能很差或不安全的查询。受限 DSL 让系统知道每个表达的语义，才能做类型检查、优化和诊断。

讲编译层时，要避免只说“转换”。更准确的说法是“结构化解析、强类型校验和语义保持的 SQL 生成”。因为系统不是简单替换 `indicator("close")` 为 `close`，还要处理窗口函数层级、CTE 阶段、日期裁剪、空值逻辑和 Doris SQL 限制。

讲执行层时，要区分本地验证和 Doris 证据。本地 SQLite 验证用于快速回归，Doris 证据用于性能证明。二者服务不同目标，不能互相替代。

讲证据层时，要把数字放在文件后面。比如 `184 passed` 来自 pytest，`37/37` 来自 official suite，36.24x 来自 Doris evidence，warning 0 来自 readiness。这样评委追问时，可以迅速指向对应报告。

### 18.4 性能亮点表达

性能亮点不应只说“使用前缀和提升性能”。更完整的表达是：长窗口滚动 SUM 在大规模行情表上会重复扫描窗口范围，查询成本随窗口和数据量增加而上升。系统识别到可优化的 `SUM(indicator(...), window)` 后，若指标配置声明支持 prefix-sum，就把窗口求和改写为前缀表差分或热点窗口列访问。

这类优化对上层 DSL 透明。用户仍然写 `SUM(indicator("volume"), 120)`，不需要知道底层表结构。编译器根据配置和语义选择 SQL 路径，并在 Explain 中记录 `PREFIX_SUM` applied。这样既降低用户使用门槛，也保留工程可解释性。

展示性能时要带上实验条件：同一 DSL，baseline 使用窗口函数，optimized 使用 prefix table 或热点列，行数一致，Doris SQL cache 禁用，多轮采样，达到 10x 以上目标。这样数字才有可信度。

如果评委问为什么不是所有查询都走 prefix-sum，应说明 prefix-sum 适用于可累加指标的滚动 SUM。对于 `MAX`、`MIN`、复杂条件、收益率或非累加指标，需要使用其他优化策略或保持窗口函数。系统不会为了追求性能数字而错误套用 prefix-sum。

### 18.5 AI 辅助边界表达

AI 辅助边界可以这样讲：系统允许中文自然语言或 LLM 产生候选 DSL，但候选只是输入草稿，不是执行结果。任何候选都必须经过 parser、semantic analyzer、SQL generator、Doris SQL validator 和 reference equivalence。直接 SQL 会被拒绝，错误指标会进入诊断，只有合法 DSL 才能继续执行。

这种设计并不排斥大模型，而是把大模型放在合适的位置。大模型擅长理解自然语言和生成候选表达，但不适合独自承担数据库执行安全和金融语义口径。确定性编译器负责后半段，让系统既有交互友好性，又有工程可靠性。

答辩中不要把 AI 辅助讲得过满。应该承认 provider 调用是可选路径，离线模板和候选验证才是可复现主路径。这样更符合竞赛评审对稳定性的期待。

### 18.6 风险边界表达

高质量项目不怕讲边界。FinDSL Forge 的边界包括：当前真实 Doris 性能证据集中在 120 日成交量滚动 SUM 的 prefix 路径；真实行情小样本用于业务展示，不用于性能证明；新增普通指标可以配置化，但新增全新函数通常需要代码和测试；provider 质量不作为核心正确性依据。

这些边界不是扣分点。相反，清楚说明边界能让评审相信团队理解自己的系统。过度承诺“所有查询都能加速”“所有自然语言都能理解”“新增任何函数都不用改代码”反而容易被追问击穿。

在项目材料中，已完成内容和后续增强要分开写。已完成内容必须能找到文件、命令和报告；后续增强可以包括更大真实数据、更多指标、更多 Doris 物化视图策略、多节点集群和更完整的 LLM 评测。两者不要混在同一张成果表里。

## 第19章 质量保障与验收解释

本章说明项目质量如何被保障。它不是测试清单的重复，而是解释为什么这些测试和报告能支撑提交质量。

### 19.1 为什么需要多层测试

FinDSL Forge 的错误可能出现在多个层面。如果 lexer 错了，合法字符可能无法识别；如果 parser 错了，优先级可能错误；如果 semantic 错了，非法表达可能进入 SQL；如果 sqlgen 错了，Doris SQL 可能语义偏离；如果 reference 错了，等价验证就失去基准；如果 Doris evidence 错了，性能结论就不可信。

因此项目需要多层测试，而不是只运行一个端到端样例。单个端到端样例能说明某条路径可用，但不能说明系统对各种组合都可靠。官方风格正例、负例、等价验证、Doris SQL validation、Demo smoke 和 readiness 共同构成质量网。

多层测试还有一个好处：失败时更容易定位。parser 测试失败说明语法层有问题，equivalence 失败说明语义或 SQL 有问题，Doris evidence 失败说明真实数据库路径有问题，Demo smoke 失败说明 API 或页面集成有问题。定位清晰，修复成本就低。

### 19.2 为什么需要负例

负例是金融系统质量的重要组成。真实用户不会永远输入正确表达，LLM 也不会永远返回合法 DSL。如果系统面对错误输入时直接崩溃、返回 Python stack trace，或者更糟糕地生成 SQL，那么它就不适合作为可控工程系统。

项目中的负例覆盖未知指标、未知函数、类型错误、非法窗口、非法日期、非法 rank 参数、直接 SQL、裸字段绕过、静态除零等情况。这些负例说明系统知道自己的边界。知道边界的系统比盲目接受所有输入的系统更可靠。

负例还可以提升答辩表现。现场展示一个错误输入，并看到系统给出稳定诊断和修复建议，会让评委直观看到系统的工程韧性。许多项目只展示成功路径，一遇到追问就显得脆弱；负例展示能弥补这一点。

### 19.3 为什么需要 evidence snapshots

`reports` 目录中的报告是本地生成物，可能随着运行时间变化而变化，也可能不纳入 Git。为了让提交版本自带可复核证据，项目提供 `submission_artifacts/evidence_snapshots`。这个目录保存轻量证据快照，让评审即使不重新运行全部脚本，也能看到当时的 readiness、official suite、Doris evidence 等关键报告。

Evidence snapshots 的价值在于绑定代码版本和证据版本。如果只提交代码，不提交证据，评委需要自己运行复杂环境；如果只提交截图，不提交报告，证据难以复核；如果报告数字和代码不一致，可信度下降。快照机制让这些信息处在同一仓库中。

导出快照后，如果又修改代码，应重新运行 readiness 和 export artifacts。否则快照仍然是旧版本证据，不能代表当前代码。这个流程虽然多一步，但能避免最终提交材料前后矛盾。

### 19.4 为什么需要 Git cleanliness

Git cleanliness 看似只是工程习惯，实际和证据可信度直接相关。如果工作区存在未提交修改，readiness 报告中的 commit hash 就不能完全代表当前文件内容。评审或队友按 commit 回溯时，可能无法恢复当时运行的状态。

因此 readiness 把 Git rollback cleanliness 作为 warning gate。最终提交前，工作区应当干净，HEAD 与 origin/main 一致或至少有明确提交记录。这样无论从 GitHub 还是 bundle 恢复，都能拿到同一版本。

如果确实有不应提交的本地文件，例如临时日志或渲染中间图片，应确认它们不会影响提交材料。对于本操作手册导出过程产生的 `reports/operation_manual_pdf_pages` 这类 QA 中间文件，可以保留在本地用于检查，但通常不需要作为正式附件提交。

### 19.5 文档质量如何判断

操作文档的质量不只看字数。好的操作文档应当让读者知道系统做什么、为什么这样做、怎么运行、看到什么算成功、遇到问题怎么处理、哪些结论不能过度解释。文档如果只有命令，不足以帮助非开发者理解；如果只有背景介绍，又无法指导真实操作。

本手册采用“说明 + 步骤 + 预期结果 + 异常处理”的方式组织内容。对于可比较的信息使用表格，对于真实流程使用编号步骤，对于解释性内容使用连续段落。这样既方便快速查找，也能保留足够语境。

文档中的 `【待补充】` 不是缺陷，而是对未确认事实的诚实标记。比如最终提交平台对视频格式的要求、本机精确硬件配置、私有 Doris 集群账号等，如果没有可靠来源，就不应虚构。正式提交前，可由负责人根据实际情况补齐。

## 第20章 材料整理与最终交付建议

本章说明最终提交前如何整理材料。竞赛项目常见问题是代码做得不少，但材料散乱，评委无法快速判断完成度。FinDSL Forge 已经有代码、报告、截图、视频、白皮书和操作手册，最后阶段的重点是整理一致性，而不是继续无节制增加功能。

### 20.1 推荐提交材料清单

推荐提交材料包括：项目源码、README、中文操作手册、中文综合操作指南、readiness 快照、Doris evidence、Demo 截图、演示视频、答辩 PPT 和必要的说明文档。若平台限制文件数量，可以优先提交源码、PDF 文档、演示视频和 evidence snapshots。

中文操作手册负责回答“怎么使用”；中文综合指南负责回答“为什么这样设计”；README 负责快速启动；readiness 负责总体验收；Doris evidence 负责性能证明；截图和视频负责现场观感。每类材料有自己的职责，不应互相替代。

如果需要压缩包提交，建议保持目录结构，不要把所有文件平铺在一个文件夹中。评审看到清晰目录，更容易找到关键材料。压缩包根目录可以包含 `README.md`、`docs`、`submission_artifacts`、`src`、`configs`、`tests`、`scripts` 和 `deploy`。

### 20.2 文档版本管理

文档应跟随代码版本管理。Markdown 是源文件，DOCX 和 PDF 是导出物。修改文档内容后，应重新导出 DOCX/PDF，并检查文件大小和 PDF 页面渲染。如果只改 Markdown 不更新 PDF，提交时很容易出现内容不一致。

本手册的 Markdown、DOCX 和 PDF 都放在 `docs` 目录下，便于统一管理。综合指南也在同一目录下。提交前可以用 `git status --short` 查看哪些文档发生变化，再决定是否提交。

如果文档经过多轮修改，建议在版本记录中说明主要变化。例如“补充 Doris 证据采集流程”“增加非开发者操作说明”“更新 official suite 数字”。这样后续维护者能快速理解文档演进。

### 20.3 PPT 与操作手册的关系

PPT 不应复制操作手册。PPT 适合展示结论、架构图、关键数字和演示路径；操作手册适合承载详细步骤、命令、异常处理和文件索引。答辩时可以把操作手册作为备查资料，而不是逐页展示。

制作 PPT 时，可以从本手册提取以下内容：项目一句话介绍、赛题痛点、总体流程、核心功能、prefix-sum 性能亮点、AI 安全边界、readiness 指标和最终提交检查。每页只放必要信息，不要把长段落塞进幻灯片。

如果 PPT 中引用数字，例如 `184 passed` 或 36.24x，应在备注或页脚写明来源文件。这样评委追问时，可以立即打开 evidence snapshot，而不是让讲解停留在口头承诺。

### 20.4 演示视频与截图管理

演示视频应围绕核心路径录制，不要试图展示所有功能。推荐一分钟到三分钟版本：中文输入生成 DSL、SQL/AST/Explain 展示、prefix-sum 示例、负例诊断、readiness 证据。短视频重在清楚，不在于把所有细节塞进去。

截图应与视频和手册一致。比如截图中如果展示 `positive 37/37`，手册和 PPT 也应写同样数字。若系统重新运行后数字变化，应重新截取关键页面。截图文件名最好能体现内容，例如 `01_nl_to_dsl_overview.png`、`04_positive_explain.png`、`07_negative_unknown_indicator.png`。

如果提交平台要求真人讲解，应提前确认视频格式、大小、时长和是否需要出镜。该信息目前属于 `【待补充】`，不能在文档中假设。录制前应关闭无关窗口和通知，避免泄露路径、密钥或私人信息。

### 20.5 最终复核顺序

最终复核建议按以下顺序进行。先运行全量 pytest，确认代码没有回归；再运行 readiness，确认核心 gate 和 warning；再导出 evidence snapshots；然后导出文档 DOCX/PDF；接着检查截图、视频和 PPT 数字；最后提交 Git、推送远端并生成 bundle。

这个顺序的原因很简单：测试和 readiness 决定证据数字，证据数字决定文档和 PPT 内容。如果先写文档再跑 readiness，可能需要反复改数字。把证据放在前面，可以减少返工。

复核完成后，不建议再做大功能修改。最后阶段的修改应尽量限定在错别字、路径说明、截图更新和格式修正。任何核心代码改动都需要重新跑完整验证，否则会破坏前面已经稳定的材料。

### 20.6 提交后的保留事项

提交后仍应保留本地仓库、GitHub 远端和离线 bundle。竞赛过程中可能需要补交材料、答辩复现或回应评审问题，保留完整环境能减少临时恢复成本。

还应保留用于生成文档的 Markdown 源文件。PDF 适合阅读，DOCX 适合编辑，Markdown 适合版本差异对比。三者都保留，后续维护会更顺畅。

如果比赛结束后继续开发，可以把竞赛提交版本打 tag，例如 `competition-submission-v1`。这样后续即使继续改功能，也能随时回到正式提交状态。是否打 tag 由团队决定：`【待补充：最终提交后是否创建 Git tag】`。

## 第21章 阅读路线与实际落地建议

本章补充不同读者如何使用这份手册。文档内容较多，如果所有人都从第一页读到最后一页，效率并不高。更好的方式是根据当前任务选择阅读路线：评审看证据，答辩看演示，开发看模块，维护看回归，交接看文件和版本。这样既能减少阅读负担，也能让文档真正服务项目落地。

### 21.1 评审人员的阅读路线

评审人员通常没有时间逐行阅读操作命令。建议先看第1章和第2章，了解项目背景、软件功能和整体运行流程；再看第10章，确认提交前验收如何判断；随后查看第17章中的完整案例，理解系统如何从业务需求走到可验证结果；最后看第19章，确认质量保障逻辑。

评审阅读时，最重要的是把“说法”和“证据”对应起来。项目说自己支持长窗口优化，就应能看到 Doris evidence；项目说自己支持官方风格正负例，就应能看到 official suite；项目说自己不让 LLM 直接执行 SQL，就应能看到 unsafe direct SQL 的拒绝证据。只要每个核心结论都能找到证据，项目可信度就会高很多。

如果评审只想快速判断项目成熟度，可以优先打开 `submission_artifacts/evidence_snapshots/submission_readiness.md`。这份报告比单张截图更可靠，因为它把测试、等价验证、Doris 证据、真实行情样本、答辩包和 Git 状态放在同一处。报告显示 warning count 0 时，说明当前提交版本没有明显未处理风险。

### 21.2 答辩人员的阅读路线

答辩人员建议先读第13章和第18章。第13章说明不同场景下该如何理解系统，第18章给出更适合现场表达的讲解口径。读完这两章后，再回到第5章和第6章熟悉页面与功能操作，最后用第10章检查提交前证据。

答辩准备时，不要试图把所有章节都背下来。手册的作用是帮助答辩人员形成清晰判断，而不是替代现场表达。现场真正需要讲清的是四件事：赛题痛点是什么，系统方案是什么，核心亮点在哪里，证据如何复核。每件事都准备一到两个例子即可。

答辩人员还应提前准备追问回答。比如评委问“为什么不用大模型直接生成 SQL”，可以引用第18章的 AI 辅助边界；问“36.24x 是否代表所有查询”，可以引用第7章和第18章的性能边界；问“新增指标怎么做”，可以引用第9章配置扩展说明。提前把追问和章节对应起来，现场会更稳。

### 21.3 开发人员的阅读路线

开发人员应先看第14章，理解 DSL 编译、语义验证、SQL 生成、reference evaluator、NL2DSL 和 readiness 各模块职责。随后看第15章，学习如何判断命令输出是否正常。最后看第9章，了解配置扩展和维护建议。

开发人员最容易犯的错误是只改能让当前样例通过的代码，而忽略 official suite 和 readiness。FinDSL Forge 的价值来自完整证据链，任何新增能力都应补齐 parser、semantic、sqlgen、reference、tests 和 docs。只在 SQL generator 中拼出一条新 SQL，不代表能力已经完成。

如果开发人员要重构代码，建议先记录当前 readiness 快照，再在小分支或明确提交中修改。重构完成后，不仅要跑 pytest，还要跑 official suite 和 readiness。对于涉及 Doris SQL 的改动，应额外检查 Doris SQL validation 和 prefix benchmark。重构不能以牺牲可复核证据为代价。

### 21.4 运维或环境配置人员的阅读路线

运维或环境配置人员应重点看第3章、第4章和第7章。第3章说明基础工具、网络和外部依赖，第4章说明如何启动本地系统，第7章说明 Doris 环境和性能证据采集。运维人员不一定需要理解每个 DSL 函数，但必须知道 Docker、MySQL 客户端、Doris FE 端口、Stream Load 和 prefix table 构建顺序。

环境配置时，建议先跑轻量验证，再跑重型 Doris 脚本。轻量验证包括 Python 版本、pytest 小范围测试、Web Demo 启动和 `verify-sql`。这些都正常后，再进入 Docker 和 Doris。这样可以避免把 Python 环境问题误判成 Doris 问题。

Doris 环境配置完成后，应保留建表、加载、前缀表重建和 evidence 采集的日志。若后续性能数字变化，这些日志能帮助判断是数据量、资源、缓存、schema 还是 SQL 路径发生变化。没有日志的性能数字很难复核。

### 21.5 项目负责人的阅读路线

项目负责人应重点看第10章、第19章和第20章。第10章告诉负责人怎样判断项目能否提交，第19章说明质量保障逻辑，第20章说明材料整理方式。负责人不一定亲自运行所有命令，但必须能判断哪些结果代表项目真实状态。

项目负责人还要控制最后阶段的节奏。越接近提交，越不应随意增加大功能。新增功能需要测试、文档、截图和讲稿同步更新，可能带来新的不稳定性。最后阶段更适合做材料一致性检查、演示彩排、证据快照刷新和备份。

如果团队成员对“是否已经完成”有分歧，建议以 readiness 和 requirement mapping 为准。口头觉得完成不够，必须有报告和文件支撑；单项功能很亮眼也不够，必须不破坏整体门禁。项目负责人需要把团队注意力从“还能加什么”拉回“现在是否稳”。

### 21.6 文档落地使用建议

这份手册可以作为三种材料使用。第一，它可以作为提交附件，让评审知道如何运行系统。第二，它可以作为团队内部操作指南，让后来者接手项目。第三，它可以作为答辩备查资料，当现场追问细节时，能够迅速找到相关章节。

为了让文档真正落地，建议在团队内部进行一次“按手册操作”的彩排。让不熟悉代码的人只看本文档，从环境检查开始，启动 Demo，运行一个正例、一个负例，查看 readiness 快照，并找到 Doris evidence。若他能顺利完成，说明文档可用；若他在某一步卡住，就说明文档还需要补充。

文档使用过程中发现的问题，应回写到 Markdown 源文件，而不是只在口头提醒。比如某条命令需要先设置代理、某个端口容易被占用、某个截图路径变化，都应更新到文档。操作文档只有随着真实使用不断修正，才会越来越可靠。

### 21.7 最后一轮人工检查

提交前的最后一轮人工检查可以按“看、跑、对、备”四个字执行。看，是查看 README、操作手册、综合指南、PPT 和截图是否一致；跑，是运行 pytest 和 readiness；对，是对照 requirement mapping 和赛题指标确认没有遗漏；备，是提交 Git、推送远端并生成 bundle。

人工检查不能完全依赖自动脚本。自动脚本能发现测试失败和证据缺失，但发现不了讲稿前后表述矛盾、截图过期、PPT 数字未更新、视频中出现旧界面等问题。这些需要人逐项看材料。竞赛项目最终呈现的是系统和材料的整体状态，任何一处明显不一致都可能影响印象。

检查时应保持克制，不要在最后时刻因为看到一个小想法就改核心代码。若发现真正影响赛题要求的问题，应修改并重新跑完整验证；若只是锦上添花的想法，可以记录到后续规划。高质量交付不是无限增加内容，而是在关键能力稳定后，把证据和表达整理到最可靠的状态。

## 附录A 常用命令速查

```powershell
# 设置本地源码路径
$env:PYTHONPATH="src"

# 全量测试
python -m pytest -q

# 编译 DSL
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))' --json

# SQL/reference 等价验证
python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json

# 中文需求生成候选 DSL
python -m findsl.cli suggest-dsl 'A股每日换手率前50%' --data-dir data/samples --json

# LLM 候选安全验证
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --json

# 官方风格套件
python -m findsl.cli official-suite --output reports/official_suite_report.md --json

# 答辩证据包
python -m findsl.cli defense-package --output reports/defense_package.md --json

# 启动 Web Demo
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1

# 生成 Doris 资产
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1

# 采集 Doris 证据
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1

# 提交前总验收
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1

# 导出提交证据快照
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

## 附录B 关键文件索引

| 文件 | 说明 |
|---|---|
| `README.md` | 项目快速说明和命令入口。 |
| `docs/architecture.md` | 架构说明。 |
| `docs/doris_runbook.md` | Doris 运行和证据采集说明。 |
| `docs/requirement_mapping.md` | 赛题要求与实现模块映射。 |
| `docs/FinDSL_Forge_中文综合操作指南.md` | 长篇综合白皮书和答辩指南。 |
| `docs/FinDSL_Forge_中文操作手册.md` | 本操作手册 Markdown 源。 |
| `submission_artifacts/evidence_snapshots/submission_readiness.md` | 最新提交证据快照。 |
| `submission_artifacts/demo_screenshots` | Web Demo 截图。 |
| `submission_artifacts/defense_video` | 一分钟演示视频。 |

## 附录C 文档版本记录

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-06-07 | v1.0 | 生成 FinDSL Forge 中文操作手册，覆盖安装、启动、功能操作、Doris 证据、维护和提交前验收。 |
