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

## 目录

第1章 引言

第2章 软件概述

第3章 运行环境

第4章 安装、配置与启动

第5章 系统界面说明

第6章 功能操作说明

第7章 Doris 环境与性能证据操作

第8章 数据、报告与提交资产管理

第9章 系统维护与配置扩展

第10章 提交前验收流程

第11章 常见问题与处理方法

第12章 使用注意事项

第13章 深度使用场景说明

第14章 主要功能模块详解

第15章 操作过程中的结果判断

第16章 面向非开发者的操作说明

第17章 完整操作案例说明

第18章 讲解口径与文档表达建议

第19章 质量保障与验收解释

第20章 材料整理与最终交付建议

第21章 阅读路线与实际落地建议

附录A 常用命令速查

附录B 关键文件索引

附录C 文档版本记录

## 第1章 引言

### 1.1 编写目的

本手册用于指导评审、答辩人员、开发维护人员和项目交接人员正确运行 FinDSL Forge。阅读者可以根据本文完成从代码仓库到本地可运行系统的准备，也可以在答辩前使用本文检查核心证据是否仍然有效。

文档重点回答四个问题：项目是什么，如何启动，如何使用主要功能，如何验证赛题要求。涉及尚需人工补充的信息，文档会使用 `【待补充】` 标记，不虚构账号、密钥、线上地址或未确认的运行参数。

### 1.2 项目背景
从项目背景继续展开看，赛题真正考察的是团队能否把“金融业务表达”转化为“数据库可以高效执行且结果可以复核”的工程链路。行情选股需求表面上只是筛选股票，实际包含很多容易出错的细节，例如交易日窗口与自然日窗口的区别、复权口径与原始价格口径的区别、跨市场合并时字段是否一致、排名截断是在过滤前还是过滤后执行。这些问题如果只靠人工解释，现场很难说清楚；如果写进编译器、配置和验证脚本中，就可以形成稳定的系统能力。

本项目的背景也与当前大模型发展状态有关。大模型已经能够理解中文需求，并能生成较完整的候选表达，但它仍然会出现幻觉、遗漏条件、误造字段和生成危险 SQL 的问题。FinDSL Forge 没有否定 AI 辅助的价值，而是把 AI 放在合适的位置：它可以帮助用户更快表达需求，但不能替代确定性编译、语义校验和数据库安全边界。这样的设计更贴近金融科技应用的真实要求，因为金融系统强调的是可解释、可审计和可回溯，而不是一次性生成结果。

对于评审而言，项目背景部分应帮助其理解：系统并不是为了做一个“把中文翻译成 SQL”的普通工具，而是为赛题中复杂行情条件、Doris 高性能执行和提交可复核证据这三个目标建立统一工程框架。后续章节中的安装、运行、验证、Doris 证据、readiness 和交付材料，都是围绕这个框架展开的。读者如果先理解这一点，再看具体命令和界面，就不会把项目误解为简单 Demo。

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
从评审视角看，本项目的价值不只在于“能生成一段 SQL”，而在于这段 SQL 的来源、边界和验证路径都能够解释清楚。金融行情选股查询包含窗口语义、排序截断、跨市场组合和长期历史数据扫描，如果系统只是把自然语言直接交给大模型生成 SQL，短时间内也许能得到看似可用的结果，但评审很难确认 SQL 是否满足原始语义，更难确认它在大规模 Doris 环境下是否稳定。FinDSL Forge 把“生成”放在辅助位置，把“编译、验证、优化和证据”放在主线位置，这一点是理解项目竞争力的关键。

DSL 在本项目中不是为了增加概念，而是为复杂查询提供一个稳定边界。金融选股表达如果直接写成自然语言，含义往往会有歧义，例如“最近一段时间”“连续上涨”“成交量明显放大”都需要进一步定义。DSL 的作用就是把这些模糊说法转为明确结构，例如窗口长度是多少、条件是否需要连续满足、排序是升序还是降序、取前多少名、日期范围是否闭区间。只有这些要素被写清楚，后续 SQL 生成和结果验证才有基础。

系统没有让大模型直接执行数据库，这是一个有意保留的安全边界。当前大模型在自然语言理解和候选表达生成方面已经很有帮助，但它并不适合作为数据库执行权限的直接拥有者。金融数据查询一旦涉及真实业务库，就会遇到安全边界、资源控制、结果可解释和审计追踪问题。若允许模型直接生成并执行任意 SQL，模型可能产生全表扫描、危险函数、非预期 join 或难以复核的聚合逻辑。FinDSL Forge 的处理方式更接近企业内部会接受的方案：大模型可以参与候选 DSL 生成，但候选 DSL 必须经过确定性解析、语义检查、SQL 安全检查和 reference 等价验证。

从维护者角度看，DSL 还能降低扩展成本。新增指标时，维护者主要更新配置映射和必要样例；新增函数时，需要补齐解析、类型检查、SQL 生成和 reference evaluator。虽然这比临时写一条 SQL 麻烦，但它把一次性工作变成可复用能力。以后遇到相同类型的行情条件，不需要重新解释每条 SQL 的写法，只需要复用已经验证过的 DSL 结构。

### 2.4 总体运行流程
从运行流程看，系统把用户可见操作和内部工程步骤分开处理。用户看到的是输入 DSL、查看 SQL、查看验证结果；系统内部实际完成的是词法解析、语法树构建、类型和函数参数校验、表字段映射、窗口语义展开、SQL 形态检查以及 evidence 记录。这样的分层使得界面可以保持简洁，同时又不会牺牲内部验证深度。对于操作人员来说，不需要理解每个类和函数的实现细节，但需要知道每个输出区域代表哪一类证据。

运行流程中的每一步都有明确失败方式。解析阶段失败通常说明 DSL 格式不合法；语义阶段失败通常说明指标、函数或参数不符合配置；SQL 生成阶段失败通常说明表达式虽然语法正确，但暂时无法映射到 Doris 可接受的形态；验证阶段失败则说明生成 SQL 与参考语义出现差异，需要进一步排查。把失败分层展示出来，可以减少排错时的盲目性，也能让答辩人员解释系统为什么没有把错误输入继续向后传递。

在正式演示中，不建议把流程图讲成抽象架构。更自然的讲法是选一条具体 DSL，从输入开始说明它如何进入 parser，如何变成 AST，如何根据配置找到指标字段，如何生成 Doris SQL，如何被 reference evaluator 复核，最后如何进入 readiness 证据。这样讲解能够把流程和真实结果联系起来，评审更容易理解系统设计不是停留在图上，而是已经落实到可运行命令和报告文件中。

总体流程还体现了项目的可维护性。未来新增函数或指标时，只要沿着这条链路补齐配置、编译、验证和文档，就能把新能力纳入同一套门禁。相反，如果绕过 DSL 直接添加零散 SQL 模板，短期内可能更快，但长期会造成结果无法统一验证、材料难以解释和扩展边界混乱的问题。因此，手册后续章节反复强调不要只改一处配置，正是为了维护这条完整流程。

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
不同角色阅读手册时，关注点并不相同。评审专家更关心项目是否满足赛题要求、证据是否可复核、性能指标是否有真实支撑；答辩人员更关心演示顺序、讲解口径和现场问题回答；开发维护人员更关心环境、测试、配置扩展和 Git 回溯；项目交接人员则需要知道哪些文件是源文件，哪些文件是导出物，哪些报告可以作为最终提交证据。文档在同一套章节中兼顾这些角色，是为了减少材料分散带来的理解成本。

对于团队内部使用来说，角色说明还能帮助分工。准备答辩的人不一定要理解每个编译器类的实现，但必须能解释 DSL、SQL、验证和 Doris evidence 的关系；负责开发的人不一定要制作视频，但必须保证正负例、测试和配置一致；负责材料的人不一定要修改代码，但必须核对 README、PPT、操作手册和 readiness 中的数字。角色边界越清楚，临近提交时越不容易互相等待或重复劳动。

实际执行中，不同角色之间也需要共享同一套证据口径。比如答辩人员引用 36.24x 加速时，开发人员应能指出对应 Doris evidence；文档人员写 184 passed 时，测试负责人应确认这来自最新 pytest；项目负责人判断是否可提交时，应以 readiness 的 Blocking gates 和 Warning count 为准。这样做能够让团队从“各说各的”转向“围绕同一套证据说明项目”。

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
在 Windows 本地开发环境中，网络问题经常表现为依赖下载失败、GitHub push 超时、Docker 镜像拉取缓慢或连接被重置。处理这类问题时，应先确认本机代理端口是否可用，再把代理变量显式传给当前命令。此前项目使用 `127.0.0.1:7897` 代理端口完成远端推送，说明在当前机器上该代理路径可用。后续若再次出现网络失败，可以优先沿用这一思路排查。

代理设置也要注意作用范围。浏览器能访问 GitHub，不代表 PowerShell、Git、pip、Docker 都自动走同一代理。不同工具可能读取不同环境变量或配置文件。对于 Git，可以临时设置 `HTTP_PROXY`、`HTTPS_PROXY` 和 `ALL_PROXY`；对于 pip，可以使用 `--proxy` 参数；对于 Docker Desktop，则可能需要在应用设置中配置代理。排查时不要把所有网络错误都归结为远端不可用，应先确认当前工具是否真正使用了代理。

项目路径中包含中文目录，这对大多数现代工具没有问题，但个别命令行程序的控制台输出会出现编码显示异常。遇到这种情况时，不要只根据终端乱码判断失败，应检查退出码、输出文件大小和实际文件内容。此前 PDF 导出时，`soffice` 控制台显示中文路径乱码，但 PDF 文件能够正常生成并渲染。类似情况在 Windows 环境中并不少见，判断时应以文件和渲染结果为准。

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
第一次运行 FinDSL Forge 时，使用者应先把它理解为一个本地工程项目，而不是一个已经部署好的线上系统。项目主要通过命令行和本地 Web Demo 提供功能，运行前需要确认 Python 环境、项目依赖、样本数据和端口状态。若需要采集真实 Doris 证据，还需要 Docker、Doris FE/BE 服务、MySQL 客户端以及可访问的 9030 端口。不同功能对应的环境要求不同，不能把 Web Demo 能启动等同于 Doris evidence 已经完成。

普通演示场景下，只要 Python 环境和项目依赖正常，用户就可以启动 Web Demo，输入 DSL，查看系统生成的 SQL、AST、Explain 和诊断信息。这个场景适合答辩开场展示，让评审直观看到系统如何从业务表达进入可执行 SQL。若要展示性能亮点，就应切换到 Doris 证据章节，说明 5,000,000 行规模数据、前缀表构建方式、基线查询和优化查询之间的差异。两类展示目的不同，现场讲解时不要混在一起。

首次运行完成后，建议操作者不要立即关闭终端，而是保留服务窗口和浏览器页面，观察一次完整请求的日志输出。日志中通常会显示请求进入、候选 DSL 生成、编译结果和验证状态。对于不熟悉项目的人来说，这些日志能够帮助理解页面背后确实在调用本地服务，而不是展示静态内容。若后续页面出现异常，保留这次成功日志也方便对比。

首次运行验证的目标是建立信心，而不是完成所有验收。它证明本地 Demo 主链路可用，但还不能替代全量测试、官方套件和 Doris evidence。很多项目在答辩前容易把“页面能打开”误认为“项目已完成”，这种判断不够严谨。FinDSL Forge 的正确操作方式是先用轻量闭环确认环境，再用测试和 readiness 确认提交状态，最后用 Doris 证据说明性能能力。

系统启动后，建议先做一次“轻量闭环验证”。这个验证不依赖 Doris，也不依赖外部 LLM provider，适合作为安装完成后的第一道确认。

1. 在浏览器打开 Web Demo。
2. 使用默认中文请求或输入“筛选A股连续三天主力净流入为正并按换手率排名前一百”。
3. 查看系统生成的候选 DSL，确认候选表达式通过验证。
4. 切换到 SQL 和 Explain 区域，确认 SQL、AST 和规则记录正常显示。
5. 切换到 Evidence 或 Rows 区域，确认验证结果为 PASS。

完成上述步骤后，可以认为本地 Demo 主链路已经可用。如果页面能打开但分析失败，优先查看启动窗口中的报错；如果页面无法打开，优先检查端口、进程和防火墙；如果只有 verification 失败，则查看样本数据和 `PYTHONPATH` 是否正确。
第一次运行 FinDSL Forge 时，使用者应先把它理解为一个本地工程项目，而不是一个已经部署好的线上系统。项目主要通过命令行和本地 Web Demo 提供功能，运行前需要确认 Python 环境、项目依赖、样本数据和端口状态。若需要采集真实 Doris 证据，还需要 Docker、Doris FE/BE 服务、MySQL 客户端以及可访问的 9030 端口。不同功能对应的环境要求不同，不能把 Web Demo 能启动等同于 Doris evidence 已经完成。

普通演示场景下，只要 Python 环境和项目依赖正常，用户就可以启动 Web Demo，输入 DSL，查看系统生成的 SQL、AST、Explain 和诊断信息。这个场景适合答辩开场展示，让评审直观看到系统如何从业务表达进入可执行 SQL。若要展示性能亮点，就应切换到 Doris 证据章节，说明 5,000,000 行规模数据、前缀表构建方式、基线查询和优化查询之间的差异。两类展示目的不同，现场讲解时不要混在一起。

手册中的命令不是要求用户机械地从头到尾全部执行，而是为不同验证目标提供入口。想确认项目代码是否健康时，优先运行 `python -m pytest -q`；想确认一条 DSL 能否编译时，运行 `compile` 命令；想确认 SQL 与参考语义是否一致时，运行 `verify-sql`；想刷新提交材料时，运行 `submission_readiness.ps1` 和 `export_submission_artifacts.ps1`。每条命令都应带着明确目的执行，执行后也应查看对应输出，而不是只看终端是否结束。

运行命令前，建议先确认当前工作目录是项目根目录。很多脚本依赖相对路径，如果在错误目录执行，可能出现找不到配置、找不到样本数据或报告输出到意外位置的问题。Windows PowerShell 中还要注意执行策略，项目提供的脚本通常使用 `powershell -ExecutionPolicy Bypass -File ...` 方式运行，就是为了减少本地策略对脚本执行的影响。若命令中包含中文或特殊字符，应优先使用 UTF-8 友好的终端环境，避免输出乱码影响判断。

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
阅读 Demo 输出时，可以按“DSL、AST、SQL、Explain、Rows、Evidence、Diagnostic”的顺序理解。DSL 是用户意图的结构化表达，AST 说明解析后的内部结构，SQL 是面向 Doris 的执行结果，Explain 说明是否走到优化路径，Rows 用于观察样本输出，Evidence 用于联系提交材料，Diagnostic 用于解释错误或警告。这个顺序能帮助非开发者把页面信息串起来，而不是把每个区域当作孤立文本。

若 Demo 返回错误，应优先看 Diagnostic，而不是直接修改代码。很多错误本身就是系统应当拦截的负例，例如未知指标、错误函数参数、非法窗口长度或不支持的组合。对评审而言，系统能够明确拒绝错误输入反而是优点，因为它说明编译器具有边界意识。只有当一个已知正例突然无法通过，或者 Demo 页面本身无法启动时，才需要进一步检查服务日志、端口占用和依赖环境。

当系统输出 SQL 时，使用者需要区分“SQL 已生成”和“SQL 已证明正确”。编译器能生成 SQL，说明 DSL 通过了语法和语义检查；reference evaluator 与 SQLite 验证通过，说明 SQL 在样本数据上与参考语义一致；Doris evidence 存在，说明相同类型的查询能够在 Doris 规模环境中执行并记录性能。三者层级不同，答辩时应按层级说明，避免把一个层级的证据说成全部证据。

界面提示信息还应与操作目的结合阅读。若操作者只是想确认编译器能工作，看到 SQL 和 AST 正常生成即可进入下一步；若操作者想准备答辩，就需要同时查看 Explain 和 Evidence；若操作者想排查错误，则应优先查看 Diagnostic 和服务端日志。不同场景下关注点不同，不能把所有提示都当作同一类信息处理。

Web Demo 中的提示信息主要分为三类。第一类是正常结果，例如候选 DSL 已验证、SQL/reference 一致、optimizer rule applied。看到这类提示时，可以继续查看 SQL、AST 和 Rows。第二类是诊断信息，例如未知指标、非法窗口、非法 rank 参数或直接 SQL 被拒绝。诊断信息不应被视为程序崩溃，它是系统有意设计的可恢复失败路径。第三类是运行时错误，例如样本数据缺失、服务端异常或外部 provider 调用失败，这类问题需要回到命令行查看日志。

答辩时应主动展示一次诊断路径。许多项目只展示成功样例，评委很难判断系统面对错误输入时是否可靠。FinDSL Forge 的诊断区能把错误码和修复建议展示出来，说明系统对无效 DSL 有明确边界，不会把错误表达继续编译成危险 SQL。

如果提示中出现 `UNSAFE_DIRECT_SQL`，说明候选内容看起来像 SQL，而不是受控 DSL。正确处理方式不是放行该内容，而是要求用户或 LLM 重新给出 FinDSL 表达式。金融场景中，拒绝直接 SQL 是安全设计的一部分。
阅读 Demo 输出时，可以按“DSL、AST、SQL、Explain、Rows、Evidence、Diagnostic”的顺序理解。DSL 是用户意图的结构化表达，AST 说明解析后的内部结构，SQL 是面向 Doris 的执行结果，Explain 说明是否走到优化路径，Rows 用于观察样本输出，Evidence 用于联系提交材料，Diagnostic 用于解释错误或警告。这个顺序能帮助非开发者把页面信息串起来，而不是把每个区域当作孤立文本。

若 Demo 返回错误，应优先看 Diagnostic，而不是直接修改代码。很多错误本身就是系统应当拦截的负例，例如未知指标、错误函数参数、非法窗口长度或不支持的组合。对评审而言，系统能够明确拒绝错误输入反而是优点，因为它说明编译器具有边界意识。只有当一个已知正例突然无法通过，或者 Demo 页面本身无法启动时，才需要进一步检查服务日志、端口占用和依赖环境。

当系统输出 SQL 时，使用者需要区分“SQL 已生成”和“SQL 已证明正确”。编译器能生成 SQL，说明 DSL 通过了语法和语义检查；reference evaluator 与 SQLite 验证通过，说明 SQL 在样本数据上与参考语义一致；Doris evidence 存在，说明相同类型的查询能够在 Doris 规模环境中执行并记录性能。三者层级不同，答辩时应按层级说明，避免把一个层级的证据说成全部证据。

## 第6章 功能操作说明

### 6.1 编译 DSL 为 Doris SQL
理解编译结果时，用户应把 DSL 和 SQL 放在一起看。DSL 代表业务表达，SQL 代表数据库执行计划的输入，两者之间不应出现语义漂移。例如 DSL 中使用 `MAX(indicator("close"), 250)`，SQL 中就应体现按股票和日期顺序计算的窗口最大值；DSL 中使用 rank 截断，SQL 中就应体现排序和限制逻辑。若 SQL 字符串很长，不必逐个字符阅读，但应抓住表名、字段名、窗口、排序和过滤条件这些关键结构。

编译命令的另一个价值是帮助开发者在不启动 Web Demo 的情况下快速定位问题。界面适合展示，命令行适合排错。若某条表达在页面中失败，可以把同一条 DSL 拿到 CLI 中运行，查看更直接的错误信息。反过来，若 CLI 能正常编译但页面显示异常，就说明问题更可能出在前端交互、服务接口或页面状态，而不是编译器核心逻辑。

对于答辩演示，建议准备一条稳定正例和一条稳定负例。正例用于展示系统能够完成编译和验证，负例用于展示系统不会把非法输入继续传递到 SQL 执行层。负例不应选择过于离谱的内容，而应选择真实用户可能犯的错误，例如指标拼写错误或窗口参数不合法。这样的演示更贴近实际使用，也更能体现系统质量。

编译结果出现变化时，需要结合变更历史判断原因。若最近修改了函数配置、指标配置或 SQL 生成逻辑，SQL shape 发生变化可能是预期结果；若没有相关改动，突然变化就需要警惕。提交前最好保留典型样例的输出截图或报告片段，方便确认最终材料中的 SQL 与当前代码一致。

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
等价验证的核心价值在于避免系统自我证明。编译器生成 SQL 后，如果只检查 SQL 字符串中是否包含某些关键字，很容易漏掉窗口边界、排序方向和日期裁剪错误。reference evaluator 使用独立路径计算预期结果，能够把“SQL 长得像正确”推进到“结果确实一致”。对于金融数据处理系统，这种结果级验证比单纯字符串检查更有说服力。

验证失败时，排查顺序要保持耐心。首先确认输入 DSL 是否属于系统支持范围，其次确认样本数据是否包含相关指标和日期，再确认 reference evaluator 与 SQL 执行器使用的数据是否一致。若这些都没有问题，再查看编译器生成的 SQL 是否在窗口分组、过滤位置或排序截断上出现偏差。不要一开始就修改测试期望值，因为那样可能把真实错误掩盖掉。

对于窗口函数，验证时尤其要关注边界样本。窗口长度为 1、窗口长度刚好等于样本天数、窗口长度超过样本天数、日期范围位于样本开头或结尾，这些场景都容易暴露隐藏问题。若系统只在普通中间日期样本上通过验证，还不能说明窗口逻辑完全稳健。后续扩展函数时，也应优先补充边界样本。

对于排名和截断逻辑，验证时要确认排序是在正确阶段执行。某些表达需要先过滤再排名，某些表达需要在市场内排名，某些表达需要跨市场合并后再截断。若执行顺序不同，SQL 仍然可能返回行，但业务含义已经改变。reference evaluator 的意义就在于用更直接的方式表达预期语义，从而发现这类不容易从 SQL 外观看出的错误。

验证结果通过后，也应保留简短解释。比如报告中不仅写 PASS，还应说明这条 DSL 覆盖了哪个函数、哪个指标和哪类窗口。这样在答辩或验收时，团队能够快速说明每个样例的价值，而不是只展示一串通过状态。高质量证据不是数量堆叠，而是每一类证据都能对应一个明确风险点。

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
采集 Doris 证据前，操作者应先确认本地 MySQL 客户端能够连接 Doris FE。这个检查看似简单，却能提前发现很多问题，例如容器未启动、端口未映射、FE 仍在初始化、Windows 防火墙拦截连接或代理设置影响本地访问。只有连接层确认正常，再执行建表、导入和查询脚本，排错成本才会比较低。

Doris 证据的可信度来自可重复过程。数据生成、schema 创建、prefix table 构建、baseline 查询和 optimized 查询都应由脚本完成，并把结果写入报告。如果只是手动执行几条 SQL，然后把终端截图放入材料，评审很难判断数据规模和查询条件是否一致。脚本化证据虽然准备时间更长，但它能把性能结果变成可复核资产。

采集过程中要注意区分“数据导入完成”和“性能证据完成”。数据导入完成只说明表中有数据，性能证据完成还需要执行基线查询、优化查询、记录耗时、计算加速比并写入 evidence 文件。若只完成导入而没有查询对比，无法支撑赛题中的性能目标。readiness 中应明确记录 Doris evidence 是否完整，而不是只记录 Doris 服务是否可连接。

如果重新采集后加速比与旧报告有差异，应先检查环境和查询是否一致。Docker 分配的 CPU 和内存、磁盘状态、Doris 缓存、数据规模、窗口长度和 SQL shape 都会影响结果。绝对耗时变化并不一定说明优化失效，但如果优化查询没有走到 prefix-sum 路径，或者数据规模明显小于报告描述，就需要修正证据或说明原因。

性能证据最终应服务于答辩表达。讲解时不要只说“加速 36.24 倍”，还要说明这是在哪个数据规模、哪个窗口场景和哪类优化路径下得到的结果。评审更关心这个数字是否可信、是否可复核、是否与赛题目标相关，而不是数字本身有多大。把数字放回场景中解释，才能体现技术深度。

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
性能结论还应避免脱离查询类型。Doris 在不同查询上的表现差异很大，简单过滤、短窗口聚合、长窗口 SUM、跨市场组合和复杂排序的瓶颈并不相同。FinDSL Forge 当前最有把握的性能亮点，是可加性指标长窗口 SUM 的 prefix-sum rewrite。讲解时把优化限定在这个场景内，结论更可信，也更容易与 evidence 对齐。

如果评审要求解释为什么不是所有查询都加速，应坦诚说明不同函数具有不同数学性质。SUM 可以通过前缀差分转换，MAX 和 MIN 通常不能直接用同样方式处理，复杂布尔条件还要考虑过滤阶段和组合语义。系统的正确做法不是强行把所有函数套进同一种优化，而是在可优化场景中应用明确规则，在不可优化场景中保持常规 SQL 和正确语义。

性能报告应当把“工程可复核”放在第一位。报告中不仅要有加速比，还应保留数据生成方式、表结构、查询 SQL、执行脚本和输出位置。若评审对数字有疑问，团队能够沿着报告找到原始证据，而不是只解释“当时跑出来是这样”。这种可复核性比单独展示漂亮数字更重要。

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
证据口径一致性还包括时间一致性。开发过程中会产生很多中间报告，其中有些来自早期实现，有些来自修复后的最新状态。如果提交材料中混入旧截图或旧报告，读者可能看到已经修复的问题，或者看到与当前 README 不一致的测试数量。因此，提交前应明确哪些文件属于最终证据快照，哪些只是开发过程产物。最终材料应优先引用 `submission_artifacts/evidence_snapshots` 中的快照，而不是随意引用 `reports` 目录下的历史文件。

材料中的数字也要有来源。正例 `37/37`、负例 `37/37`、pytest `184 passed`、Doris 5,000,000 行、36.24x 加速这些数字都不是装饰信息，而是评审判断项目完成度的重要依据。每一个数字都应能追溯到报告或脚本输出。若未来重新运行后数字变化，应更新所有相关材料，或者在文档中说明新旧证据的差异。

口径一致并不意味着所有材料写法完全相同。README 可以简短，操作手册可以详细，PPT 可以提炼，视频脚本可以口语化；但核心事实必须一致。比如 PPT 中可以把“reference evaluator 与 SQLite 执行器”简化为“独立等价验证”，但不能把它说成“直接由 Doris 自动证明正确”。表达可以面向不同场景调整，事实不能变。

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
维护配置时，最重要的原则是不要只改一处。一个新指标如果只写进 `indicators.json`，但没有样本数据、测试样例和文档说明，后续很容易出现“配置看起来存在，实际运行却不可用”的情况。一个新函数如果只实现 SQL 生成，而没有 reference evaluator 和负例检查，也会削弱系统的可信度。配置修改完成后，应至少运行编译验证、等价验证和负例验证；若扩展涉及 Doris 性能路径，还应补充 Doris smoke query 或 evidence。

函数扩展是项目中风险较高的维护动作，因为函数一旦进入 DSL，就会影响用户表达、SQL 生成和结果解释。维护者在扩展函数时，应先写清楚函数语义，而不是直接写代码。例如函数是按交易日窗口计算，还是按自然日区间计算；遇到空值时是忽略、补零还是返回空；窗口不足时是否产生结果；排序字段是否需要按市场和股票分组。这些语义如果没有先确定，后续实现很容易出现测试通过但实际含义不清的问题。

指标扩展看似简单，实际也需要认真处理。金融指标往往具有业务含义，同名字段在不同数据源中可能口径不同。例如成交额、成交量、换手率、主力净流入、涨跌幅等字段，可能涉及复权、单位、百分比表示、市场口径和缺失值处理。如果配置中只写字段名，不说明含义和单位，用户在写 DSL 时就容易误解结果。文档中对常用指标的说明不必写成论文，但应保证足够清楚。

测试维护不应只追求数量。对于 FinDSL Forge，关键风险包括解析歧义、窗口边界、排名截断、跨市场组合、未知指标拒绝、危险 SQL 拦截、prefix-sum 改写和 Doris 证据一致性。若测试只覆盖大量简单表达式，而不覆盖这些风险点，数字再好看也无法充分说明质量。因此维护测试时，应优先补充能暴露语义问题的样例。

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
答辩开场不宜把所有技术点一次性铺开。更好的方式是先用一句话说明项目主线：FinDSL Forge 将金融行情选股 DSL 编译为 Apache Doris SQL，并通过独立语义验证和 Doris 规模证据证明正确性与性能。这个主线包含四个关键词：DSL、Doris SQL、语义验证、性能证据。后续所有演示都应围绕这四个关键词展开，避免让评审觉得项目只是功能堆叠。

推荐的演示顺序是先展示正例，再展示负例，然后展示性能证据，最后展示 readiness 总报告。正例让评审看到系统能完成任务；负例让评审看到系统不会盲目接受错误输入；性能证据让评审看到系统不是停留在功能层面；readiness 总报告则把测试、证据和提交状态收束到一个可信结论。这个顺序符合评审理解节奏，也能减少现场切换混乱。

答辩时应避免使用“完全颠覆”“绝对领先”“全自动解决所有问题”这类夸张说法。FinDSL Forge 的优势在于边界清楚、证据完整和工程链路扎实，不需要靠夸张语言包装。更稳妥的表达是：系统在赛题限定范围内实现了 DSL 到 Doris SQL 的确定性编译，覆盖官方风格正负例，提供 reference 等价验证，并在 Doris 规模数据上验证了 prefix-sum 优化效果。

若评审问“为什么不用大模型直接生成 SQL”，可以回答：金融数据库执行需要可审计、可验证和可控的边界，大模型适合生成候选表达，但不适合直接拥有数据库执行权。本项目让候选 DSL 经过确定性编译器、SQL 安全检查和 reference 等价验证后再进入执行路径，这样既利用了 AI 的表达能力，也保留了工程系统的可靠性。

建议演示顺序为：

1. 打开 Web Demo，输入中文需求，生成并验证候选 DSL。
2. 展示 SQL 标签，说明系统生成的是 Doris SQL，不是 LLM 直接 SQL。
3. 展示 AST 与 Explain，说明语法树、日期下推和 prefix-sum 规则。
4. 切换到 official positive 的 prefix-sum 示例，展示前缀表路径。
5. 切换到 negative 示例，展示未知指标诊断和修复建议。
6. 打开 readiness 或 evidence snapshot，展示 `37/37`、`184 passed`、Doris 10x+ 证据和 warning 0。

答辩时不要把所有命令都现场运行一遍。现场重点是说明主线和证据，长耗时 Doris 重采集应作为已生成报告展示。

### 10.4 验收判定标准
验收判定标准应尽量具体。若只写“功能完整、运行稳定、性能良好”，读者无法判断依据。对于 FinDSL Forge，更合适的判定方式是看正向功能是否覆盖核心 DSL，负向功能是否能拒绝非法输入，reference 验证是否通过，Doris evidence 是否存在真实规模，readiness 是否无阻塞项，提交材料是否能互相印证。这些标准既能落到文件和命令上，也能减少主观判断。

功能完整并不等于支持所有可能的金融表达。赛题项目的完整性应理解为：在赛题要求范围内，系统覆盖主要表达类型，并提供清晰扩展路径。若某些超出范围的复杂策略暂未支持，只要系统能够明确拒绝并说明原因，就不应被视为核心缺陷。相反，如果系统为了显得强大而接受不明确表达，却生成无法验证的 SQL，才是真正风险。

性能达标也应按证据判断。系统已经保留 5,000,000 行 Doris 数据规模和 36.24x 长窗口加速证明，这比单纯口头说“查询很快”更有价值。验收时应看报告中是否包含基线查询、优化查询、耗时和加速比，并确认这些查询对应赛题关注的长周期场景。若未来硬件不同导致绝对耗时变化，应说明环境差异，但不应省略可复核过程。

文档验收同样重要。一个项目即使代码完成，如果文档无法指导运行，评审也很难在有限时间内确认能力。合格的操作手册应让读者知道从哪里启动、运行什么命令、如何判断结果、证据在哪里、常见问题如何处理。若文档只提供命令清单而没有解释，读者遇到异常时仍然无法独立操作。因此，本手册大量增加解释性段落，是为了让文档真正承担交付作用。

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
Doris 连接失败时，操作者不要急于修改 SQL。连接失败通常发生在执行 SQL 之前，更多与服务状态、端口、客户端、网络和容器配置有关。应先确认 Docker Desktop 是否运行，Doris FE 和 BE 容器是否启动，9030 端口是否映射到本机，MySQL 客户端是否在 PATH 中，当前命令是否使用了正确主机和端口。只有连接建立后，才需要继续排查 schema、数据和查询语法。

如果 MySQL 客户端能启动但无法连接 Doris，应观察错误信息。连接被拒绝通常说明端口未开放或服务未就绪；认证失败说明用户名、密码或认证方式不匹配；连接超时可能与防火墙、容器网络或代理有关。Windows 环境中，本地代理有时会影响外网访问，但访问 `127.0.0.1` 的 Doris 端口通常不应走外部代理。遇到异常时，应结合命令输出和 Docker 日志判断。

Doris 刚启动时，FE 和 BE 需要一定初始化时间。此时立即连接可能失败，并不代表部署错误。可以等待片刻后重试，或查看容器日志确认服务状态。若多次重试仍失败，再检查端口映射和容器健康状态。把这些排查步骤写清楚，是为了避免操作者把环境问题误判为项目代码问题。

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
使用系统时，应避免在证据采集过程中随意中断脚本。Doris 数据导入、prefix table 构建和性能查询可能需要一定时间，中途关闭终端可能导致数据不完整或报告只写入一部分。若确实需要中断，应在重新运行前清理中间状态，确认表数据、报告文件和 readiness 不会混用旧结果。对于提交证据来说，半截报告比没有报告更容易造成误导。

修改配置前，应先明确修改目的。若只是为了让某条样例通过而临时改字段名，可能会破坏其他样例；若只是为了追求更短 SQL 而绕过验证，可能会削弱系统可信度。配置、编译器和 reference evaluator 应作为一套整体维护。任何影响 DSL 语义的修改，都应重新运行相关测试和 readiness。

使用 AI 辅助入口时，操作者应保持审核意识。候选 DSL 即使来自大模型，也只是候选，不代表已经可执行。系统会对候选进行语法、语义和安全检查，用户也应阅读候选表达是否符合原始需求。若候选漏掉日期范围、窗口长度或排序条件，应修改后再验证。AI 能降低表达门槛，但不能替代用户对业务需求的确认。

提交材料中不要包含敏感信息。API key、数据库密码、真实生产主机地址、个人隐私数据和未经授权的行情数据截图，都不应进入公开仓库或比赛提交包。若需要说明某个配置项，应使用占位符或示例值。安全边界不是额外要求，而是金融科技项目的基本要求。

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
评审验收场景下，读者最关心的是系统能力是否与赛题要求真正对应。此时不宜把文档讲成普通使用说明，而应把每个操作入口和赛题指标联系起来。比如 Web Demo 不是单纯的页面展示，它承担的是可视化说明 DSL 输入、SQL 输出和诊断反馈的作用；official suite 不是普通测试集合，它承担的是证明系统覆盖赛题风格表达的作用；Doris evidence 也不是普通性能截图，它承担的是证明目标数据库上存在真实规模收益的作用。

在评审验收中，最容易失分的情况不是某个按钮不好看，而是材料无法证明系统声称的能力。若文档中说支持长窗口加速，就必须能找到对应脚本、报告和指标数字；若文档中说支持负例拒绝，就必须能找到负例套件和错误诊断；若文档中说支持 AI 辅助，就必须说明 AI 只生成候选 DSL，不能绕过安全验证。每一项说法都应能回到文件和命令上，这样评审追问时才不会出现口径断裂。

评审验收还会关注系统边界。一个成熟的竞赛项目不需要宣称自己解决了所有金融查询问题，而要清楚说明当前覆盖范围和扩展方式。FinDSL Forge 当前面向赛题 19 中的行情选股 DSL、Doris SQL 生成和长窗口优化，已经具备正负例覆盖、reference 等价验证和 Doris 规模证据。对于超出 DSL 支持范围的通用 SQL、复杂投资策略回测或生产级权限系统，应说明属于后续扩展方向，而不是把原型说成万能平台。

准备评审材料时，建议把验收路径设计成“先总览、再抽查、再深入”。总览看 README 和 readiness，抽查看 Web Demo、官方套件和 Doris evidence，深入时再看配置、编译器、测试和报告。这样的路径符合评审时间有限的现实，也能让项目亮点在短时间内被看到。操作手册承担的作用，就是把这条路径写清楚，让读者不用靠团队现场口头引导也能理解材料组织。

在评审验收场景中，操作者不应把系统介绍成一个简单的“自然语言转 SQL 工具”。这个说法过于粗略，也容易让评委误以为项目只是套了一层大模型接口。更准确的表达是：FinDSL Forge 是一套面向金融选股 DSL 的确定性编译与验证系统，中文输入只是入口之一，核心能力在于把受限 DSL 稳定编译为 Doris SQL，并用多条证据链证明语义正确和性能有效。

评审人员首先会关心系统能否覆盖赛题中的关键语义。这里的关键语义包括 `then` 的阶段化筛选与排名、`CONS/EXIST` 的连续和存在条件、窗口函数、收益率计算、日期区间、跨市场布尔组合、配置化指标以及 prefix-sum 长窗口优化。操作人员在展示时不必把所有语法都逐项展开，但应当用一两个代表性案例说明系统不是只支持单表简单过滤，而是能够处理多个语义组合。

评审人员还会关心结果是否可信。此时不要只展示 SQL 字符串，因为 SQL 字符串本身不能证明语义正确。更好的展示方式是先展示 DSL，再展示 AST，随后展示 Doris SQL 和 Explain，最后展示 SQL/reference equivalence 或 readiness 报告。这样可以让评审看到系统有完整的输入、解析、编译、优化和验证过程。对于金融科技类项目，这种可解释链路比单纯展示“运行成功”更有说服力。

如果评审追问性能，应直接说明性能证据来自 Doris cluster evidence，而不是来自本地 SQLite timing。SQLite 的存在价值是快速语义回归，Doris evidence 才是长窗口性能证明。当前项目保留 5,000,000 行 Doris 规模证据，说明 120 日成交量滚动 SUM 在 prefix 热点路径上达到 36.24x 加速。这个数字应当带着实验边界一起讲，避免让人误以为所有查询都固定加速 36 倍。

评审验收时还可能关注“新指标是否真的可以配置化扩展”。答复时应说明：普通指标可以通过 `configs/indicators.json` 声明表、列、类型和 prefix-sum 元信息，项目中也有 config-only indicator extension 的防守证据；但如果新增的是全新函数或全新语义类别，仍然需要补充语义分析、SQL 生成和 reference evaluator。这样的回答既体现配置化能力，也不会夸大系统边界。

### 13.2 答辩演示场景
答辩演示场景下，操作人员需要把技术链路讲得既准确又容易理解。开场不宜直接展示大量代码，也不宜长时间讲抽象背景。更自然的方式是先给出一个金融选股需求，例如“筛选连续资金流入且按换手率排名的股票”，然后说明人工写 SQL 容易在窗口、日期和排序上出错，系统因此引入受限 DSL 和确定性编译。评审先理解问题，再看系统解决方案，接受度会更高。

演示时应控制节奏。第一步展示中文需求或 DSL 输入，说明用户意图如何进入系统；第二步展示 DSL 和 AST，说明系统不是直接生成自由 SQL；第三步展示 Doris SQL 和 Explain，说明编译器如何落地执行形态；第四步展示 Rows 或 Evidence，说明结果经过验证；第五步展示一个负例，让评审看到系统能够拒绝错误输入。这个顺序比随意切换页面更稳定，也便于答辩人员记忆。

如果现场时间较短，可以只演示一个正例、一个负例和一份 readiness 报告。正例负责展示能力，负例负责展示边界，readiness 负责展示全局质量状态。若时间更充裕，再打开 Doris evidence 说明 5,000,000 行规模和 36.24x 加速。不要为了展示更多内容而让演示变得散乱，评审通常更看重主线清晰和证据可信，而不是页面切换数量。

答辩人员还要准备应对追问。若评审问“生成 SQL 是否一定正确”，不能简单回答“一定正确”，而应说明系统通过 reference evaluator 和 SQLite 执行器进行等价验证，并保留 Doris evidence。若评审问“AI 在系统中做什么”，应说明 AI 只生成候选 DSL，最终能否执行由编译器和验证器决定。这样的回答既稳妥，也能体现团队对工程边界的理解。

答辩演示最重要的是节奏。很多项目在功能上并不弱，但现场讲解时把命令、代码、截图和报告混在一起，听众很快失去主线。FinDSL Forge 的演示建议围绕“用户表达、编译生成、优化解释、结果验证、异常处理、性能证据”六个动作展开。每个动作都对应一个明确的得分点，避免把演示变成漫无目的的页面切换。

第一步适合从中文需求开始。可以输入“筛选A股连续三天主力净流入为正并按换手率排名前一百”，让系统生成候选 DSL。此时要强调，中文输入只是帮助用户降低表达门槛，系统并没有让大模型直接访问数据库。候选 DSL 仍然进入确定性编译器，必须通过语义校验和 reference 验证。

第二步展示 DSL 和 AST。这里可以说明，AST 是系统理解 DSL 的结构化结果，它让后续语义检查和 SQL 生成有稳定基础。对于评委来说，看到 AST 的意义在于确认系统不是简单字符串替换，而是有真正的语法结构处理。

第三步展示 SQL 和 Explain。SQL 说明系统最终面向 Doris 执行，Explain 则说明编译器为什么应用某些规则，例如日期下推、滚动窗口特征层、prefix-sum rewrite、Doris SQL validation 等。讲解时不要只念规则名，而要用自然语言解释：“这个规则的作用是把窗口函数从 WHERE 中移出去，避免生成 Doris 不友好的 SQL”；或者“这个规则把长窗口 SUM 改写为前缀表访问，减少重复窗口扫描”。

第四步展示结果验证。Rows 或 Evidence 区域能证明 SQL 输出与参考语义一致。这里可以强调 reference evaluator 是独立路径，不是 SQL generator 自己验证自己。这样能回应评审对正确性的关切。

第五步展示负例。推荐使用未知指标 `clos` 或直接 SQL 候选，让系统返回诊断和修复建议。负例展示的目的不是证明用户会犯错，而是证明系统面对错误输入时不会悄悄生成危险 SQL。金融系统尤其需要这种失败边界。

第六步展示 readiness 和 Doris evidence。此时可以打开 `submission_artifacts/evidence_snapshots/submission_readiness.md`，展示 `184 passed`、正例 `37/37`、负例 `37/37`、Doris 证据 PASS 和 warning count 0。最后用一句话收束：“前面演示的是交互路径，这里展示的是可复核证据。”这样的收尾比单独展示截图更有力量。

### 13.3 开发调试场景
开发调试场景下，最重要的是把问题缩小到具体层级。若一条表达式无法运行，先判断是 DSL 解析失败、语义校验失败、SQL 生成失败、等价验证失败，还是 Doris 执行失败。不同层级对应不同排查路径。解析失败通常查看语法和 token；语义失败查看函数参数、指标配置和类型规则；SQL 失败查看 compiler 输出；验证失败查看 reference evaluator 和样本数据；Doris 失败则查看 schema、连接、数据导入和 SQL 兼容性。

开发者不应把 Web Demo 当作唯一调试入口。Web Demo 适合观察完整链路，但命令行更适合快速重复测试。调试时可以先用 CLI 跑最小表达式，再逐步增加窗口、日期、排名和市场条件。这样能够判断是哪一个条件引入问题。若一开始就使用复杂表达式，错误可能同时涉及多个模块，排查效率会很低。

调试中还要注意保留失败样例。一个失败样例如果能稳定复现，就应转化为测试用例或记录到 issue 中。不要只在终端里临时修改到通过，因为下一次重构可能再次引入同样问题。FinDSL Forge 作为编译系统，最有价值的测试往往来自真实失败场景。每修复一个边界问题，就把对应样例纳入测试，系统质量会逐步提高。

开发者修改编译器时，应同步考虑 reference evaluator。只改 SQL 生成而不改参考语义，可能导致验证失败；只改 reference 而不改 SQL 生成，也可能让测试期望脱离真实执行。两条路径需要保持独立，但语义定义必须一致。这个平衡是项目质量的核心之一，也是后续维护中最需要耐心的地方。

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
DSL 编译模块是整个系统的中枢，它把用户表达从文本转成可以被数据库执行的结构。评价这个模块时，不能只看它能否输出 SQL，还要看它是否在输出之前完成了必要的限制和检查。一个好的编译模块应当知道哪些表达可以接受，哪些表达必须拒绝，哪些表达需要给出清晰诊断。对于金融查询系统而言，拒绝错误输入与生成正确 SQL 同样重要。

编译模块的实现价值还体现在可解释性上。用户输入一条 DSL 后，系统不仅给出最终 SQL，还能展示 AST 和 Explain。AST 说明系统如何理解表达结构，Explain 说明编译器应用了哪些规则。这些中间结果使系统不再是黑盒，也让评审能够看到从业务表达走向 Doris SQL 的过程。若只有最终 SQL，评审很难判断它是确定性编译产物，还是某种不可控生成结果。

在后续扩展中，编译模块应继续保持保守策略。遇到暂未支持的语义，应明确报错，而不是生成含糊 SQL。短期看，宽松接受输入似乎能让系统显得功能更多；长期看，它会增加错误结果风险，也会让 reference 验证难以维护。竞赛项目追求的是可信可证明的能力，不是无限放宽输入范围。

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
Reference Evaluator 的存在，使项目能够把正确性证明从“开发者相信编译器”变成“另一条路径复核编译器”。它不追求在大数据上高性能执行，而追求语义表达清晰、结果可对照。对于样本数据和官方风格用例来说，这条路径足以发现许多 SQL 生成错误，例如窗口边界偏移、排序方向错误、过滤位置错误和缺失值处理不一致。

等价验证模块也帮助团队形成更稳的开发习惯。每当新增函数或指标时，开发者需要思考 reference 应该如何计算，这会反过来逼迫团队把函数语义定义清楚。如果一个函数无法用 reference 清晰表达，说明它的语义本身可能还没有想明白。把验证作为开发的一部分，比事后靠人工检查 SQL 更可靠。

在答辩中介绍 Reference Evaluator 时，可以用“独立验算”这个更容易理解的说法。系统不是只相信自己生成的 SQL，而是用另一套计算路径在样本数据上验算结果。这个解释贴近评审直觉，也能突出项目的工程严谨性。对于金融数据系统而言，能解释结果为什么可信，比单纯展示更多功能更重要。

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
Readiness 总验收模块相当于项目的提交前体检。它把分散在测试、官方套件、Doris evidence、真实行情样本、文档和 Git 状态中的信息汇总到同一个入口，让项目负责人不用逐个目录查找。对于竞赛交付来说，这种总入口非常重要，因为提交前最怕遗漏某个关键门禁，或者材料中仍然引用过期证据。

阅读 readiness 时，应重点看结论区和阻塞项。若 Blocking gates passed 为 true，说明关键门禁没有失败；若 Warning count 为 0，说明没有需要特别解释的提醒；若某个模块出现 warning 或 fail，应沿着报告中的路径打开原始文件。readiness 不是为了替代详细报告，而是为了把详细报告组织起来，帮助团队快速判断项目是否处于可提交状态。

Readiness 也能帮助团队控制最后阶段的改动。若每次修改后都重新运行 readiness，团队就能知道新改动是否破坏了测试、证据或 Git 状态。若只在最后一天运行一次，发现问题时可能已经来不及排查。因此，readiness 应被看作日常质量门禁，而不是提交前才临时运行的形式步骤。

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
Doris Evidence 的结果判断不能只看报告中有没有“PASS”字样，还要看数据规模、查询类型、耗时记录和加速比是否完整。若报告缺少数据规模，评审无法判断性能结论是否建立在足够规模上；若报告只给出优化查询耗时而没有基线查询耗时，评审无法判断加速比如何计算；若报告没有 SQL 或脚本路径，评审无法复核查询是否与赛题要求相关。

判断 Doris Evidence 时，还要关注优化适用边界。prefix-sum 适合可转化为区间求和的滚动 SUM 场景，不应被包装成所有查询的通用加速方法。若系统对不适合的查询保持常规窗口 SQL，这是合理行为，不是功能缺失。真正需要证明的是：当查询满足优化条件时，系统能够识别并生成 Doris 友好的优化 SQL；当查询不满足条件时，系统能够保持语义正确。

如果 evidence 中出现 warning，应具体分析 warning 的含义。有些 warning 只是提示环境差异或可选文件缺失，不影响核心结论；有些 warning 则可能说明数据规模不足、证据过期或 Git 状态不干净。提交前应尽量把 warning 降到 0，若确实保留，应在文档中说明原因。评审更能接受清楚解释的 warning，而不是被隐藏的问题。

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
对于非开发者来说，理解系统能力的最好方式不是阅读源码，而是先完成一条从输入到结果的演示链路。打开 Web Demo 后，选择默认样例，观察系统如何从中文需求或 DSL 生成结构化表达，再生成 Doris SQL，并展示验证结果。这个过程能够直观说明系统不是单纯的文档项目，而是已经具备可运行的编译和验证能力。

如果只想快速了解项目亮点，可以重点看三个地方。第一个是 DSL 与 SQL 区域，它说明系统能把业务表达落地为数据库查询；第二个是 Diagnostic 区域，它说明系统能拒绝错误输入；第三个是 Doris evidence 或 readiness 报告，它说明系统有规模性能证据和提交前门禁。只要这三个地方能讲清楚，非开发者就能把握项目主线。

非开发者阅读时不需要理解每个测试文件，但需要知道测试和证据的作用。测试证明代码没有明显回归，official suite 证明赛题表达覆盖，Doris evidence 证明目标数据库性能，readiness 证明提交状态。这些材料共同构成项目可信度。如果只看界面而不看证据，很容易低估项目工程深度。

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
这个案例适合用来解释窗口查询为什么比普通过滤更复杂。普通过滤只需要判断某一天的字段值是否满足条件，而滚动成交量累计需要把当前日期之前若干个交易日纳入计算。若窗口边界处理不当，结果可能多算或少算；若日期区间处理不当，可能把区间外数据错误纳入最终结果。系统通过 DSL 明确窗口长度和日期范围，再由编译器生成对应 SQL，能够减少人工手写 SQL 的风险。

在讲解这个案例时，可以把重点放在“计算窗口”和“结果筛选”的区别上。计算窗口可能需要使用目标日期之前的数据，但最终输出只应包含用户指定日期范围内的结果。很多 SQL 错误正是把这两个范围混为一谈，导致边界日期结果不正确。Reference Evaluator 在这里能够帮助检查 SQL 是否保持同样语义。

该案例也适合连接 Doris 性能亮点。长窗口 SUM 查询在大规模数据上容易重复扫描窗口内数据，prefix-sum 优化可以把区间求和转化为前缀差分。若评审已经理解滚动成交量累计的业务含义，再解释 prefix-sum 加速就会自然很多。性能优化不是孤立技巧，而是从具体业务查询中抽象出来的工程能力。

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
未知指标诊断案例看起来只是一个小错误处理，实际上很能体现系统边界。金融数据字段很多，用户输入时很容易把 `close` 写成 `clos`，或者把某个数据源字段名当成 DSL 指标名。如果系统直接生成 SQL，错误可能要到数据库执行阶段才暴露；如果系统在语义校验阶段就发现未知指标，并给出接近项建议，用户就能更早修正问题。

这个案例适合在答辩中作为负例展示。负例展示的目的不是证明用户会犯错，而是证明系统面对错误输入时不会失控。评审看到系统能把错误定位到指标层，并给出清楚诊断，会更容易相信项目不是简单的字符串拼接。对于隐藏测试来说，稳定错误码和修复建议也有价值，因为它们说明系统能够处理非理想输入。

维护未知指标诊断时，应保证建议项来自真实配置，而不是写死在某个样例中。若未来新增指标，诊断建议也应自动反映配置变化。这样可以保持系统扩展后的用户体验，不会出现新增指标能编译但错误提示仍然停留在旧列表中的情况。

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
直接 SQL 候选拒绝案例是 AI 辅助边界的典型说明。大模型有时会根据用户需求生成一段完整 SQL，看起来似乎可以直接执行，但这与本项目的安全设计相冲突。系统要求输入必须是受控 DSL，而不是任意 SQL。这样做并不是为了限制用户，而是为了保证后续能够进行语义校验、SQL shape 检查和 reference 等价验证。

在金融场景中，直接执行模型生成 SQL 的风险很高。SQL 可能引用不存在的表或字段，可能执行过宽的扫描，也可能绕过系统预期的日期和市场限制。即使某次 SQL 恰好可用，也难以保证每次都符合业务语义。FinDSL Forge 通过拒绝直接 SQL，把风险拦在执行前，使 AI 辅助保持在候选表达层。

答辩讲解时，可以把这个案例与系统核心原则联系起来：用户可以借助 AI 生成候选，但系统只接受通过 DSL 编译器和验证器的表达。这个原则让项目既跟上大模型辅助开发和交互的趋势，又不把数据库安全交给不可控生成结果。对于金融科技创新项目来说，这种边界设计本身就是重要亮点。

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
赛题痛点可以从三个层次表达。第一层是业务表达复杂，金融选股条件经常包含窗口、排名、跨市场和日期约束，人工写 SQL 容易出错。第二层是数据库执行复杂，Doris 面向大规模分析，SQL shape、分区、前缀表和窗口函数都会影响性能。第三层是比赛交付复杂，评审不仅看功能，还看证据、文档、演示和可回溯性。FinDSL Forge 的方案正是同时回应这三个层次。

讲痛点时不要泛泛说“金融数据量大、查询效率低”。更有力的说法是说明具体场景，例如长窗口滚动 SUM 会重复聚合历史数据，人工 SQL 容易把日期过滤放错位置，LLM 直接生成 SQL 难以审计。把问题讲具体，后面的 DSL 编译、reference 验证和 prefix-sum 优化才会显得自然。评审需要看到问题与方案之间有因果关系，而不是看到一堆彼此独立的技术名词。

痛点表达还要避免把竞品或传统方法说得过于简单。手写 SQL 并不是完全不可用，它在小规模和简单查询中很直接；LLM 生成 SQL 也不是毫无价值，它能帮助用户表达需求。项目真正的观点是：在赛题要求的可信、高性能、可复核场景中，仅靠手写或仅靠生成都不够，需要确定性编译和证据链把风险控制住。这样的表达更客观，也更容易被专业评审接受。

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
性能亮点应与场景绑定表达。不要只说系统“性能好”，而要说系统针对长窗口滚动 SUM 查询提供 prefix-sum rewrite，并在 5,000,000 行 Doris 规模数据上保留 36.24x 加速证据。这样的表达包含了查询类型、优化方法、数据规模和结果数字，信息完整，评审也能判断它是否符合赛题要求。

解释性能时，可以用通俗但准确的方式说明前缀和。普通滚动窗口每到一个日期都要重新计算窗口内若干天的数据，窗口越长，重复计算越明显；前缀和提前保存从起点到当前日期的累计值，计算某个区间时只需要做两次前缀值相减。这个思路在算法上并不神秘，但把它稳定落到 Doris SQL、数据表和证据脚本中，才是项目工程价值所在。

性能亮点也要说明边界。prefix-sum 主要适用于可加性指标的区间求和，不适合所有聚合函数。对于 MAX、MIN、复杂布尔条件或无法转化为前缀差分的查询，系统应保持常规 SQL 或采用其他优化路径。把边界讲清楚，反而能体现项目严谨性。评审通常更信任知道自己能力范围的系统，而不是宣称所有场景都能加速的系统。

性能亮点不应只说“使用前缀和提升性能”。更完整的表达是：长窗口滚动 SUM 在大规模行情表上会重复扫描窗口范围，查询成本随窗口和数据量增加而上升。系统识别到可优化的 `SUM(indicator(...), window)` 后，若指标配置声明支持 prefix-sum，就把窗口求和改写为前缀表差分或热点窗口列访问。

这类优化对上层 DSL 透明。用户仍然写 `SUM(indicator("volume"), 120)`，不需要知道底层表结构。编译器根据配置和语义选择 SQL 路径，并在 Explain 中记录 `PREFIX_SUM` applied。这样既降低用户使用门槛，也保留工程可解释性。

展示性能时要带上实验条件：同一 DSL，baseline 使用窗口函数，optimized 使用 prefix table 或热点列，行数一致，Doris SQL cache 禁用，多轮采样，达到 10x 以上目标。这样数字才有可信度。

如果评委问为什么不是所有查询都走 prefix-sum，应说明 prefix-sum 适用于可累加指标的滚动 SUM。对于 `MAX`、`MIN`、复杂条件、收益率或非累加指标，需要使用其他优化策略或保持窗口函数。系统不会为了追求性能数字而错误套用 prefix-sum。

### 18.5 AI 辅助边界表达
AI 辅助边界的表达要特别谨慎。项目可以说明大模型能够帮助用户从中文需求生成候选 DSL，但不能说系统依赖大模型直接生成最终 SQL。更准确的说法是：AI 提供候选，编译器负责准入，验证器负责复核，Doris evidence 负责证明目标数据库执行和性能。这样既体现了大模型时代的创新点，又没有牺牲金融系统所需的安全性和可审计性。

如果评审追问“没有大模型是否还能运行”，应明确回答可以。项目默认核心链路不依赖外部 LLM provider，CLI、pytest、SQLite 验证、Web Demo 默认样例和 Doris evidence 都可以在无密钥情况下运行。LLM 入口是增强体验的可选能力，不是系统正确性的必要条件。这个回答能够消除评审对外部 API、网络稳定性和模型幻觉的担忧。

在材料中也应避免把 AI 写得过重。若全文都围绕大模型宣传，反而会掩盖项目真正扎实的编译器、验证器和 Doris 优化能力。更好的写法是把 AI 放在用户表达层，说明它降低了 DSL 使用门槛；把核心正确性放在确定性编译和证据链上，说明系统不会因为候选来自 AI 就放松校验。

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
项目验收时，界面只能说明系统具备可演示入口，不能单独证明系统质量。FinDSL Forge 的验收应同时检查功能、正确性、性能、文档和提交材料。功能验收看 DSL 是否能编译出 Doris SQL；正确性验收看 reference 和 SQL 结果是否一致；性能验收看 Doris evidence 和 prefix-sum 加速；文档验收看操作手册、综合指南和 requirement mapping 是否能解释系统；提交材料验收看截图、视频、报告和 Git 状态是否完整。

正确性验收应重点查看 reference evaluator。因为 SQL 生成本身由编译器完成，如果再用同一套逻辑判断正确性，就容易形成自我证明。独立 reference evaluator 的意义在于用另一条路径计算预期结果，从而降低编译器错误被掩盖的风险。验收时可以选择几条代表性 DSL，运行 `verify-sql`，查看 reference 和 SQL 结果是否一致。

对于窗口函数，正确性验收要特别小心。窗口查询容易在边界日期、分组字段、排序顺序和缺失数据上出错。若只是检查 SQL 字符串中出现了 `SUM` 或 `OVER`，并不能说明语义正确。应结合样本数据和结果行判断窗口长度是否符合预期，日期范围是否正确裁剪，排名是否在筛选后执行。手册中反复强调这些细节，是因为它们正是行情 DSL 编译的高风险点。

文档质量还要看读者能否独立完成操作。真正可用的操作手册不是把所有命令列出来，而是让读者知道为什么运行这些命令、运行后看什么、出现异常时如何判断。若一个不熟悉代码的人能够根据手册启动 Demo、运行正负例、找到 evidence、理解 readiness 结论，就说明文档具备实际交付价值。

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
文档版本管理不只是保存文件名中的日期。真正有用的版本管理应能回答三个问题：这一版文档对应哪一次代码提交，文档中引用的测试和证据来自哪一次运行，DOCX/PDF 是否由同一份 Markdown 导出。如果这三个问题回答不清，后续团队很难判断某份文档是否仍然有效。

Markdown 适合记录内容变化，Git 适合记录版本历史，DOCX 和 PDF 适合作为正式交付物。三者之间应保持清楚关系。修改正文时先改 Markdown，再导出 DOCX/PDF；调整 Word 样式时，应记录样式处理步骤；如果比赛平台只要求 PDF，也仍应保留 Markdown 和 DOCX，方便后续修改和复盘。

版本记录表也应写得克制。没有确认的修订人、单位、指导教师和正式版本号，不应随意填写真实名称。可以使用 `【待补充】` 或团队后续确认的信息。正式材料中最重要的是准确，不是看起来填满。宁可保留明确占位，也不要编造无法核实的信息。

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
提交后仍然要保留回溯意识。远端仓库保存的是代码和文档历史，本地 bundle 或压缩包保存的是当时提交材料的整体状态，两者各有作用。若后续需要证明某个版本已经具备某项能力，可以通过 Git 提交号找到源文件，再通过提交包查看当时交付给评审的正式文件。这样的双重备份能够减少“代码有了但材料找不到”或“材料有了但源文件不可编辑”的问题。

最终提交材料应形成闭环，而不是各自独立存在。README 负责快速说明项目是什么和如何开始；操作手册负责详细说明安装、运行、使用、验收和维护；综合指南负责提供更完整的方案解释和答辩口径；requirement mapping 负责把赛题要求逐项映射到实现；readiness 负责给出提交前状态；截图和视频负责展示可视化运行效果。每份材料都有自己的位置，缺一项都会影响整体表达。

材料闭环最重要的是一致性。若 README 写 184 个测试通过，PPT 写 180 个，readiness 写 184 个，评审会疑惑哪个数字是真实的。若操作手册说 Doris evidence 在一个目录，提交包中却放在另一个目录，评审会增加查找成本。提交前应统一核对所有关键数字、路径和术语，尤其是测试数量、正负例数量、Doris 数据规模、加速比、Demo 截图目录和视频目录。

Markdown 是源文件，便于版本管理和后续修改；DOCX 是正式 Word 交付文件，便于编辑、打印和按学校或比赛要求调整格式；PDF 是最终阅读和提交文件，便于保持版式稳定。三者应来自同一份内容，不应各自手动维护。若只修改 DOCX 而不改 Markdown，后续很难追踪变更；若只修改 Markdown 而不重新导出 DOCX/PDF，提交文件就会落后于源文件。

中文正式文档的排版习惯与网页文档不同。网页文档可以使用较大留白、灵活字体和卡片式结构，但软件说明书、课程设计说明书和项目验收文档更强调打印、装订和长期保存。因此，Word 版应采用 A4 纵向页面，设置合适页边距，正文使用小四号宋体，标题使用黑体，段落首行缩进，行距保持舒适。这样的格式看起来不花哨，却更符合中文正式提交材料的阅读预期。

后续维护文档时，应优先修改 Markdown 源文件，再重新导出 DOCX 和 PDF。若比赛要求提供特定 Word 模板，可以在导出后基于模板调整样式，但仍应把正文变更回写 Markdown。这样可以保证内容版本有清晰历史，也方便 Git 比较差异。对于只影响 Word 样式的修改，可以记录在提交信息中，说明内容未变、格式更新。

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
最后一轮人工检查还应关注文档本身的阅读感。若某些章节连续出现同样的句式，或者每个模块都机械写成“功能说明、操作步骤、注意事项”，读者会明显感到模板化。正式中文技术文档更自然的写法，是根据章节内容调整表达方式：背景章节多解释项目缘由，操作章节写清动作和反馈，验收章节强调判断标准，维护章节说明风险和处理原则。不同章节有不同语气，整篇文档读起来才不会生硬。

人工检查时可以让团队成员扮演不同角色阅读。答辩人员看演示路径是否顺畅，开发人员看命令和路径是否准确，维护人员看配置扩展说明是否可执行，项目负责人看材料闭环是否完整。不同角色发现的问题不同，综合起来才能提高文档质量。若所有检查都由同一个熟悉项目的人完成，很容易忽略外部读者真正会卡住的位置。

最后不要在临近提交时大幅改动核心代码。若人工检查发现的是文档不清、截图过期或材料路径不一致，应优先修正文档和材料；若发现的是影响赛题要求的功能问题，才进入代码修复和完整验证。项目越接近提交，越需要区分“必须修复的问题”和“可以后续优化的想法”。稳定交付不是把所有想法都塞进去，而是让已经完成的能力以最清楚、最可靠的方式呈现出来。

提交前还应再次确认 Git 状态和远端同步。文档、DOCX、PDF、截图、证据和代码若只存在本地未提交状态，就不能算真正完成。Git 提交号是后续回溯的重要依据，远端 push 是团队协作和备份的重要保障。对于重要版本，可以额外保留 bundle 或压缩包，避免网络仓库不可访问时影响提交和复盘。

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





