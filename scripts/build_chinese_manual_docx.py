from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "FinDSL_Forge_中文综合操作指南.docx"
SOURCE_MD = ROOT / "docs" / "FinDSL_Forge_中文综合操作指南.md"

TITLE = "FinDSL Forge 中文综合操作指南与技术白皮书"
SUBTITLE = "面向中国研究生金融科技创新大赛赛题 19 的产品、架构、算法、部署、验证与答辩文档"
VERSION = "v1.0"
GENERATED_AT = datetime.now().strftime("%Y-%m-%d %H:%M")


REFERENCE_LINKS = [
    (
        "软件创新赛项目开发文档模板",
        "https://oa.csu.edu.cn/preview/%E9%99%84%E4%BB%B65%EF%BC%9A%E9%A1%B9%E7%9B%AE%E5%BC%80%E5%8F%91%E6%96%87%E6%A1%A3docx.pdf",
        "参考其面向竞赛提交的项目概述、设计、实现、测试和使用说明组织方式。",
    ),
    (
        "Diataxis 文档框架",
        "https://diataxis.fr/",
        "参考其将教程、操作指南、解释说明和参考资料分层组织的思想。",
    ),
    (
        "Google Developer Documentation Style Guide",
        "https://developers.google.com/style",
        "参考其面向开发者文档的清晰性、任务导向和一致术语要求。",
    ),
    (
        "中文技术文档写作风格指南",
        "https://zh-style-guide.readthedocs.io/zh-cn/latest/",
        "参考中文技术写作中术语一致、句式清晰和避免口语化表达的原则。",
    ),
    (
        "openEuler 文档中心",
        "https://docs.openeuler.org/zh/",
        "参考大型开源项目按安装、管理、开发、参考和社区协作拆分文档的组织方式。",
    ),
    (
        "OpenHarmony 文档中心",
        "https://docs.openharmony.cn/",
        "参考复杂工程系统面向开发者、应用构建和系统能力说明的分层结构。",
    ),
    (
        "Apache Doris 官方文档",
        "https://doris.apache.org/docs/",
        "参考 Doris 建表、自动分区、Stream Load、窗口函数和集群运行相关说明。",
    ),
]


REQUIREMENT_TABLE = [
    ("DSL 解析与 AST", "lexer、parser、ast_nodes", "能够从选股表达式生成标准化 AST，并在 Demo 中展示。"),
    ("语义校验", "semantic、diagnostics", "未知指标、非法窗口、错误 rank 参数、直接 SQL 等在生成 SQL 前被拦截。"),
    ("Doris SQL 生成", "sqlgen、doris_sql", "生成 CTE、窗口函数、rank、date_between 下推和 prefix-sum 查询。"),
    ("正确性证明", "reference、executor、equivalence", "SQL 执行结果与独立 Pandas 语义参考结果一致。"),
    ("性能优化", "prefix-sum、hot-window materialization", "5,000,000 行 Doris 证据中达到 36.24x 加速。"),
    ("AI 辅助", "nl2dsl、llm_adapter", "自然语言只生成 DSL 候选，候选必须经过编译器和参考验证。"),
    ("工程交付", "scripts、reports、submission_artifacts", "readiness、Doris 证据、答辩包、bundle 备份形成闭环。"),
]


COMMAND_TABLE = [
    ("运行测试", "python -m pytest -q", "验证 parser、semantic、SQL、Doris 证据解析、Demo API 等回归用例。"),
    ("启动 Web Demo", "powershell -ExecutionPolicy Bypass -File .\\scripts\\serve_demo.ps1", "打开本地评委演示控制台。"),
    ("生成 readiness", "powershell -ExecutionPolicy Bypass -File .\\scripts\\submission_readiness.ps1", "生成提交前总验收报告。"),
    ("导出证据快照", "powershell -ExecutionPolicy Bypass -File .\\scripts\\export_submission_artifacts.ps1", "把 reports 中轻量证据复制到可版本化提交包。"),
    ("复现 Doris 规模证据", "powershell -ExecutionPolicy Bypass -File .\\scripts\\prepare_doris_scale_evidence.ps1 -ProxyUrl \"http://127.0.0.1:7897\"", "启动 Doris、生成 5M 数据、Stream Load、重建 prefix、采集证据。"),
]


EVIDENCE_TABLE = [
    ("Pytest 回归", "169 passed", "覆盖编译器、参考执行、Demo、安全、收益率算子和 Doris 证据采集逻辑。"),
    ("官方风格正例", "32/32", "覆盖窗口、排名、日期裁剪、多表指标、prefix-sum、收益率和热点窗口。"),
    ("官方风格负例", "34/34", "覆盖未知指标、非法窗口、非法日期、RET 嵌套窗口、直接 SQL、安全诊断。"),
    ("Doris 规模证据", "36.24x", "5,000,000 行数据，baseline window 与 optimized prefix 行数一致。"),
    ("Readiness", "Warning count: 0", "阻塞门禁与警告门禁均通过。"),
]


ARCHITECTURE_LINES = [
    "中文需求 / DSL / LLM 候选",
    "  -> Lexer 与 Parser 生成 AST",
    "  -> Semantic Analyzer 检查指标、函数、参数与安全边界",
    "  -> SQL Generator 生成 Doris SQL 与 rewrite trace",
    "  -> Doris SQL Validator 检查单语句、安全表引用和窗口位置",
    "  -> SQLite/Pandas 等价验证证明语义正确",
    "  -> Apache Doris 执行并采集 EXPLAIN、行数和延迟证据",
    "  -> Web Demo、Readiness Report、Submission Artifacts 对外展示",
]


CHAPTER_INTROS = {
    "文档框架、读者对象与阅读路线": "本章先把文档本身讲清楚。竞赛交付材料最怕两种情况：一种是只有漂亮叙述，评委找不到证据；另一种是只有命令和截图，读者看不出项目判断。本手册需要同时承担说明书、白皮书和答辩索引三种职责，因此这里先交待读者、结构和参考框架，后续章节才能围绕同一套标准展开。",
    "项目背景、赛题理解与解题策略": "赛题 19 的竞争点不在于能否生成一条 SQL，而在于能否把金融 DSL、Doris 执行、长窗口优化和可复核证据组织成一个完整系统。本章从题目本质、评分指标、技术风险和获奖策略四个角度拆解项目目标，目的是把后面的架构与算法放回赛题语境中，而不是孤立展示工程功能。",
    "产品介绍与用户价值": "产品章节回答“这个系统对谁有用、为什么有用”。金融科技比赛虽然看重算法和工程，但评委同样会判断作品是否像真实产品。项目价值来自两端：一端降低策略研究者表达复杂筛选条件的成本，另一端保留数据工程团队需要的安全、诊断、复现和性能边界。",
    "系统总体架构": "架构不是一张流程图的装饰，而是项目能否长期演进的骨架。本章把输入、编译、验证、执行和展示分层展开，说明各模块如何协作、证据如何生成、后续指标和数据源如何扩展。读完这一章，评委应能判断项目不是几个脚本拼在一起，而是一套边界清楚的工程系统。",
    "DSL 语言设计": "语言设计决定了项目的上限。FinDSL 没有追求通用 SQL 的自由度，而是把金融筛选里高频、可验证、可优化的结构抽象出来。这样做看似收窄了表达范围，却换来更强的语义检查、更稳定的 SQL 生成和更清楚的性能优化入口。",
    "编译器前端与语义分析": "编译器前端承担“把用户输入变成可信内部结构”的责任。词法、语法和语义三个阶段分别解决文本边界、结构表达和业务合法性问题；配置注册表则把指标和数据源从核心逻辑中剥离出来。本章重点说明这些基础模块为什么直接影响安全、扩展和隐藏用例能力。",
    "Doris SQL 生成与安全边界": "SQL 生成是赛题交付中最容易被误解的部分。真正有价值的生成器不是拼接几段固定查询，而是根据 AST、函数依赖、窗口语义、数据来源和优化条件构造可执行、可解释、可验证的 Doris SQL。本章同时说明安全检查的必要性，尤其是 AI 辅助输入不能直接越过 SQL validator。",
    "性能优化算法与实验设计": "性能章节是项目最有技术门槛的部分之一。长窗口查询在金融数据中非常常见，也最能体现 Doris 物理设计、prefix-sum 改写和热点窗口物化的价值。本章不只解释优化原理，还说明实验如何避免缓存、样本过小和行数不一致等常见误判。",
    "AI 大模型辅助与安全设计": "大模型能力适合改善输入体验，但金融数据库执行不能建立在不可控输出上。本章把 AI 放在候选生成层，强调所有候选都要进入同一条编译、验证和诊断链路。这样的设计既顺应当前 AI 辅助开发和业务表达的趋势，也避免把项目讲成缺少安全边界的文本转 SQL 玩具。",
    "数据模型、Doris 部署与环境操作": "数据和环境章节面向实际落地。没有清楚的数据模型，DSL 语义无法稳定；没有可复现的 Doris 环境，性能证据就缺少根基。本章说明当前最小数据模型、Doris 表设计、本地 Docker 路径、Stream Load 流程和真实数据接入边界，为后续复现实验提供操作依据。",
    "功能操作指南": "操作章节按使用者真正会做的事情来组织，而不是按源码目录罗列。先确认基础环境，再使用 CLI 编译和诊断，随后启动 Web Demo，最后运行 readiness。这个顺序能让新接手的人快速建立信心，也能让答辩人提前排练现场流程。",
    "测试、验证与质量保障": "质量章节把项目可信度落到具体测试和报告上。当前验证不是单一 pytest，也不是单一 Doris 截图，而是由单元测试、官方风格套件、语义等价、Doris 规模证据和提交包快照共同支撑。这里的重点是证明项目状态可以被重复检查。",
    "竞赛答辩与材料组织": "答辩材料要服务现场沟通。技术团队容易陷入细节，但评委在有限时间内需要听到清楚的痛点、方案、证据和创新点。本章给出主线、演示节奏、PPT 结构和得分点映射，帮助团队把已经完成的工程成果讲成一条有说服力的故事。",
    "工程管理、Git 回溯与风险控制": "竞赛项目越接近提交，工程管理越重要。一次未提交的本地修改、一个没同步的证据快照、一次错误覆盖，都可能让前期工作变得难以回溯。本章说明 Git、bundle、风险清单和质量门禁的配合方式，保证项目不仅能做出来，也能稳稳交出去。",
    "后续增强路线": "最后一章把增强方向和已完成内容分开。真实数据、多节点 Doris、物化视图、真实 LLM provider 和更多 DSL 算子都值得继续做，但它们不能替代当前已经完成的核心链路。本章的作用是给评委展示项目成长空间，同时保持对当前交付状态的诚实。",
}


CHAPTER_DEEP_DIVES = {
    "文档框架、读者对象与阅读路线": [
        "文档写作首先要服务评审判断。评委在有限时间内不会替团队拼接散落信息，所以材料必须主动交代问题、方案、证据和边界。把摘要、得分点、架构、算法、操作和附录放在同一份 Word 中，是为了减少信息断裂。",
        "企业技术文档的语气应当克制。它可以有判断，但不应过度宣传；可以强调亮点，但必须给出文件、命令或数据来源。本手册后续反复使用 pytest、official suite、Doris evidence、readiness 和 Git bundle 这些具体资产，目的就是让结论落地。",
        "阅读路线也体现产品思维。评委需要最快看到核心价值，开发者需要能复现，答辩人需要能讲清楚，维护者需要知道后续怎么改。把这些读者分开考虑，文档才不会变成一篇只有作者自己看得懂的长说明。",
        "排版上，本文保留长段落，因为赛题分析、算法解释和风险判断需要完整语境；同时用表格处理证据映射和命令速查。这样的形式比纯表格更适合深度阅读，也比纯散文更适合临近提交前检查。",
    ],
    "项目背景、赛题理解与解题策略": [
        "赛题 19 有明显的综合性。它要求理解金融筛选表达，掌握数据库 SQL 生成，知道 Doris 的执行特点，还要能把性能优化做成可复现实验。任何一条线薄弱，最终作品都容易变成“能演示但不够扎实”。",
        "解题时需要把大模型热度放回正确位置。当前 AI 能帮助理解自然语言，却不能保证生成 SQL 的安全性和口径稳定性。因此项目选择编译器作为核心，大模型或模板只作为候选入口，这个判断是项目能否获得高分的基础。",
        "赛题评分通常会关注功能覆盖、复杂查询、性能、创新和交付质量。项目已经覆盖窗口、排名、连续、存在、日期和辅助表 join，并用 prefix-sum 做出明显性能亮点。文档需要把这些点串起来，让评委看到它们不是零散功能。",
        "策略上应少讲宏大愿景，多讲已完成证据。真实 Doris 5M 实验、36.24x 加速、正负例套件和 readiness warning 0 都是硬材料；未来多节点 Doris、真实 LLM provider 和更多算子则放在增强路线中，保持已完成与规划之间的清楚边界。",
    ],
    "产品介绍与用户价值": [
        "产品价值来自“把复杂性放到系统内部”。策略用户不该被迫记住窗口函数的 SQL 细节，也不该承担日期裁剪是否正确的风险；他们更关心表达条件和查看结果。系统把这些复杂性封装在编译器、验证器和 Doris 适配层中。",
        "对数据平台团队而言，受限 DSL 比开放 SQL 更容易治理。指标从 registry 进入，表引用由系统生成，危险语句在 validator 中被拦截，错误通过 diagnostic code 返回。这样的机制比单纯提供一个 SQL 输入框更接近企业内部工具。",
        "产品还要能解释自己。AST、trace、explain、Rows 和 Evidence 标签页不是装饰，它们让用户看到系统每一步做了什么。金融科技场景中，可解释往往和可用同等重要，因为结果需要被研究员、工程师和评审共同理解。",
        "如果后续继续产品化，重点不应先做复杂营销页，而应增强工作流：样例管理、历史查询、证据导出、指标注册可视化、真实数据源配置和异常诊断面板。这些功能与当前架构自然衔接，也更贴近真实用户需要。",
    ],
    "系统总体架构": [
        "架构分层的意义在于降低相互污染。自然语言模块可以持续迭代，但不能影响编译器安全；Doris 证据可以独立重采，但不能改变 DSL 语义；Web Demo 可以调整 UI，但不能绕过后端验证。边界清楚，项目才经得住多轮修改。",
        "输入层和编译层之间的契约是 DSL。只要候选能变成 DSL，后续就进入确定性路径；如果候选无法通过 DSL 规则，就被诊断拒绝。这个契约让 AI、手写 DSL、样例选择都可以共用一条后端链路。",
        "验证层承担的是可信度建设。Pandas reference evaluator、SQLite executor、Doris SQL validator 和 Doris evidence collector 分别从不同角度检查输出。它们不是重复劳动，而是在不同风险面上建立防线。",
        "展示层不只是“前端页面”。readiness 报告、defense package、submission_artifacts 和 Word 手册也属于展示层的一部分。比赛交付面对的是人，系统必须把内部证据整理成评委能理解的形式。",
    ],
    "DSL 语言设计": [
        "DSL 的成功标准不是语法看起来复杂，而是能自然表达赛题所需的金融筛选。filter、then、rank 对应关系流转，indicator 对应业务指标，MA、SUM、MAX、MIN、RET、CONS、EXIST 对应时间序列计算，date_between 对应交易日期约束。",
        "受限语法让系统可以主动阻止危险输入。用户不能写 `DROP TABLE`，也不能把任意 SQL 塞进查询；指标必须通过 registry 解析，函数必须经过参数检查。这种约束使 DSL 更适合金融科技竞赛，而不是削弱能力。",
        "语言设计还影响性能优化。如果 SUM 的窗口参数和指标来源在 AST 中清晰存在，prefix-sum rewrite 才能安全触发；如果所有内容都只是字符串，优化器就只能做脆弱的文本匹配。",
        "后续扩展 DSL 时要保持“少而准”。新增一个成熟算子，比新增十个没有 reference 和测试的名字更有价值。每个算子都应有语义定义、错误条件、SQL 生成、参考实现和官方风格用例。",
    ],
    "编译器前端与语义分析": [
        "前端模块决定了系统面对脏输入时的表现。真实用户不会总是输入干净样例，括号、引号、大小写、日期格式和参数名都可能出错。Lexer 和 Parser 把这些问题分层处理，能让错误更早、更准确地暴露。",
        "AST 是后端所有判断的基础。语义分析、SQL 生成、explain、Demo 展示和 reference evaluator 都依赖同一棵结构树。只要 AST 保持稳定，系统的多个模块就能围绕同一语义协作，而不是各自重新解释文本。",
        "语义分析应当尽量贴近业务规则。窗口为正整数、rank 参数互斥、top 与 desc 匹配、指标必须存在，这些规则都比数据库层错误更接近用户理解。把它们放在编译前端，可以提升诊断质量。",
        "Registry 是工程扩展的关键。没有注册表，新增指标会散落在 parser、SQL generator、reference 和测试里；有了注册表，扩展流程就能被文档化和自动化。这个设计也方便答辩时说明项目可维护性。",
    ],
    "Doris SQL 生成与安全边界": [
        "SQL 生成器必须了解数据库执行顺序。窗口特征、排名、过滤和 join 不能随意排列，否则 SQL 可能看起来正确却无法执行，或者执行结果和 DSL 语义不一致。项目通过 CTE 层级把这些语义拆开。",
        "Doris 适配不是把表名换成 Doris 表名。分区字段、colocate group、prefix 表、热点窗口列、EXPLAIN 采集和 MySQL 兼容端口都会影响最终落地。文档把这些资产集中说明，便于评委看到真实数据库工作量。",
        "安全边界要在 SQL 生成后再次确认。即使 SQL 由系统生成，也可能因为代码缺陷产生异常结构；validator 的存在能在执行前多一道防线。对于允许 AI 候选输入的系统，这一点尤其重要。",
        "trace 和 explain 让 SQL 生成变得可讨论。评委可以看到系统是否使用 prefix、是否通过 Doris SQL validation、是否做了日期处理。没有这些解释，生成器再复杂也很难在答辩中被快速理解。",
    ],
    "性能优化算法与实验设计": [
        "性能优化要先找到真实瓶颈。短窗口、小数据和缓存命中都可能制造误导，无法代表赛题中“长范围查询加速”的要求。项目选择 120 日成交量和 5M 数据，是为了把优化放在足够有压力的场景里。",
        "prefix-sum 的数学原理并不复杂，难点在工程落地。需要维护交易日 row_no，保证股票分区，处理日期范围，构建 prefix 表，并让 SQL generator 在合适条件下触发 rewrite。这些细节共同决定优化是否可靠。",
        "实验设计必须同时验证速度和结果。只快不准没有意义，所以 Doris evidence 把行数一致作为硬条件；只看结果不看计划也不够，所以报告还检查 baseline window 与 optimized prefix table 的计划标记。",
        "性能结论要保持准确边界。当前 36.24x 是特定长窗口 SUM 路径上的真实 Doris 证据，不能自动推广到所有函数。这样写不会削弱项目，反而说明团队理解不同查询的优化条件。",
    ],
    "AI 大模型辅助与安全设计": [
        "当前 AI 发展使自然语言入口变得可行，但金融场景不能把模型输出直接当成事实。模型可能漏条件、改口径、生成危险 SQL，也可能在格式上不稳定。安全环正是为这些现实问题设计。",
        "NL2DSL 和 LLM adapter 的共同目标是生成候选，而不是替代编译器。候选通过 deterministic compiler 后才有意义；没有通过，就应该返回诊断。这个过程让 AI 能力成为增益，而不是新的风险源。",
        "安全设计还要关注失败展示。项目内置包含有效候选、拼写错误和直接 SQL 的样例响应，能在答辩中现场展示系统如何筛选模型输出。这样的演示比单纯说“我们防幻觉”更有说服力。",
        "后续接入真实模型时，评估指标应包括命中率、拒绝率、危险输出比例、验证耗时和人工修复成本。只有这些数据可见，AI 辅助才不会停留在概念层。",
    ],
    "数据模型、Doris 部署与环境操作": [
        "数据模型保持最小但完整，是为了让项目先把核心语义跑通。daily_quote、money_flow 和 stock_universe 已经能够覆盖行情、资金流和市场属性，也能支撑窗口、排名、连续和辅助表 join 等赛题重点。",
        "Doris 部署材料需要同时服务新手和评委。新手关心怎么启动、怎么连接、怎么导入数据；评委关心表设计是否合理、证据是否真实、性能路径是否能复现。runbook 和 SQL 文件要同时满足这两类需求。",
        "Windows 本地环境有一定复杂度，尤其是 WSL2、Docker Desktop、代理和 PATH。文档把这些组件拆开说明，能减少用户把所有问题混在一起排查。比赛前环境稳定性往往决定演示心态。",
        "真实数据接入是加分项，但必须和合成性能基准分开描述。真实样例让业务更可信，合成数据让实验可重跑；两者的价值不同，不应互相替代。",
    ],
    "功能操作指南": [
        "操作指南最好按日常工作流排序，而不是按命令字母顺序排序。用户通常先检查环境，再编译表达式，再诊断错误，再启动 Demo，最后生成 readiness。文档遵循这个顺序，读者更容易照着完成任务。",
        "CLI 和 Web Demo 面向不同场景。CLI 适合开发、测试和报告生成；Web Demo 适合评委演示和业务沟通。两者共享后端能力，因此展示效果不同，技术结论一致。",
        "诊断操作应成为演示的一部分。很多比赛项目怕展示失败，但成熟系统应当能优雅地失败。通过负例展示错误码和修复建议，反而能证明项目覆盖了真实用户输入的不确定性。",
        "readiness 是最后的收口工具。它把测试、证据、artifacts 和 Git 状态集中检查，适合在每次重要提交前运行。把这个命令变成团队习惯，能显著降低最终提交风险。",
    ],
    "测试、验证与质量保障": [
        "质量保障不是单靠测试数量。更重要的是测试是否覆盖了真正会失分的地方：语义漂移、窗口边界、日期裁剪、安全绕过、Doris 计划不符合预期、证据缺失和提交包不一致。项目的测试体系围绕这些风险展开。",
        "official suite 让赛题理解变成可执行资产。每个正例或负例都代表一种评审可能关注的输入形式；当它进入 JSONL 后，团队就不需要靠记忆维护覆盖面。这个机制适合持续扩展。",
        "语义等价验证提供了比人工读 SQL 更可靠的检查。Pandas reference 和 SQL executor 来自两条路径，能互相发现问题。对于编译器项目，这种“双路径证明”比普通结果截图更有技术含量。",
        "Doris 规模验证则补上真实数据库维度。小样本等价只能说明语义，不能说明长窗口性能；Doris evidence 通过 EXPLAIN、COUNT 和延迟数据把性能结论落到实际执行环境。",
    ],
    "竞赛答辩与材料组织": [
        "答辩要让评委先理解问题，再理解技术。直接从模块名开始讲，容易让听众失去上下文；从金融筛选复杂、LLM 直接 SQL 风险和长窗口性能瓶颈开始，项目价值会更自然地浮现。",
        "演示动作应少而准。每次点击都要回答一个问题：输入是否友好，编译是否可信，优化是否有效，错误是否可控，提交是否可复核。无关页面和过长代码都应避免出现在现场主流程里。",
        "PPT、Word 手册、Demo 和 evidence snapshots 要互相支撑。PPT 给结论，Demo 给体验，手册给细节，证据快照给复核。四者角色不同，混在一起会让材料显得杂乱。",
        "答辩问答要提前准备边界问题。比如为什么不用模型直接生成 SQL，为什么 SQLite 不能证明 Doris 性能，36.24x 是否适用于所有查询，真实数据如何接入。这些问题都能从手册中找到稳妥回答。",
    ],
    "工程管理、Git 回溯与风险控制": [
        "工程管理的目标是让项目在任何关键节点都能回到可用状态。Git commit 记录远端历史，bundle 保留离线备份，readiness 标识可提交状态，submission_artifacts 固化证据。它们合在一起，才是真正的回溯体系。",
        "越接近截止，越要避免无证据改动。一个看似很小的文案、脚本或配置修改，都可能影响生成结果或操作路径。重要修改后重新生成文档、运行测试并提交，是防止最后混乱的基本纪律。",
        "风险清单要写得具体。比如“真实 LLM 未接入”比“AI 能力待完善”更明确，“多 BE Doris 未实测”比“性能还可优化”更可执行。具体风险才能对应具体行动。",
        "质量门禁应与团队分工结合。有人负责代码，有人负责文档，有人负责演示和证据，但最终都要汇总到同一套 readiness 和 Git 状态中。这样团队协作不会因为材料分散而失控。",
    ],
    "后续增强路线": [
        "后续规划要体现优先级。真实数据样本能提升业务可信度，真实 LLM provider 能提升输入体验，多节点 Doris 能提升企业化说服力，更多 DSL 算子能扩展场景。它们都重要，但投入产出不同。",
        "如果目标是进一步冲击奖项展示，优先级建议是：先补真实数据小样本，再把已采集的 Demo 截图整理进 PPT 和答辩视频，然后考虑真实 LLM provider，最后再推进多节点 Doris。这样能把有限时间用在最容易被评委感知的增强上。",
        "技术深化则可以围绕 Doris 继续做。物化视图、增量 prefix 维护、多 BE 集群、查询 profile 和资源隔离，都能让项目更接近真实数据平台。但这些工作需要明确实验环境，否则容易花费很大却难以展示。",
        "DSL 扩展要坚持证据先行。每新增一个方向，都要同步补语义定义、reference、测试、样例、文档和 Demo。只有这样，路线图才不会变成口号清单，而会变成可逐步实现的工程计划。",
    ],
}


CHAPTERS = [
    (
        "文档框架、读者对象与阅读路线",
        [
            ("优秀竞赛文档的共性框架", "文档框架", "从竞赛文档模板、开源项目文档和开发者指南中抽象出项目背景、需求、设计、实现、测试、部署、操作、风险和附录九类内容。", "本手册在每一类内容中都给出本项目对应的证据位置，避免出现只有叙述没有验证的文档。", "阅读者可以先看摘要和得分点映射，再按角色进入产品、算法、部署或答辩章节。"),
            ("本文档的定位", "文档定位", "本文档不是普通 README，也不是只给评委看的宣传稿，而是完整的技术白皮书、操作手册和答辩材料索引。", "它同时服务于开发者、答辩人、评审专家和后续维护者，因此既要说明为什么这样设计，也要说明怎样复现。", "文档采用论文式段落展开，表格用于对照和核查，命令块用于复现实验。"),
            ("读者对象与使用方式", "读者对象", "如果读者是评委，应重点阅读赛题理解、竞争亮点、性能证据和答辩脚本；如果读者是开发者，应重点阅读架构、DSL、SQL 生成、测试与部署。", "如果读者是团队成员，可以按操作步骤直接启动 Demo、运行 readiness、导出 evidence snapshots。", "这种多入口结构来自大型开源项目文档的经验：同一个项目需要解释性内容、任务型内容和参考型内容并存。"),
        ],
    ),
    (
        "项目背景、赛题理解与解题策略",
        [
            ("赛题 19 的本质问题", "赛题理解", "赛题要求将金融选股领域语言编译为高性能 Apache Doris SQL，本质上是一个领域特定语言、数据库优化和工程交付交叉的问题。", "它不只是字符串替换，也不是把自然语言交给大模型生成 SQL，而是要在金融可审计场景中保证语义稳定、结果正确和性能可验证。", "因此项目把核心能力拆成编译器、参考语义、Doris 适配、性能优化、AI 辅助和证据链六条线。"),
            ("核心评价指标", "评价指标", "项目围绕编译正确率、编译延迟、长窗口加速、可扩展指标、可复现交付和现场演示六个方向组织实现。", "当前 readiness 报告显示编译 P95 毫秒级、官方风格正负例全通过、Doris 规模证据达成 10x 以上目标。", "这些指标不是口头承诺，而是由 pytest、official suite、Doris evidence 和 submission artifacts 共同形成证据闭环。"),
            ("主要技术风险", "风险分析", "最大风险是把复杂金融表达翻译错、把窗口语义裁剪错、把 LLM 幻觉结果误当 SQL 执行、或者只在小样本中证明性能。", "FinDSL Forge 的策略是让每个风险都有独立防线：语义分析防止非法 DSL，参考解释器防止 SQL 语义漂移，Doris SQL validator 防止危险查询，Doris 集群证据防止纸面性能。", "这种风险拆解方式比单纯追求功能数量更适合竞赛高分，因为评委关心的不只是能运行，还关心为什么可信。"),
            ("国家级奖项导向策略", "竞赛策略", "国家级奖项通常要求技术完成度、工程成熟度、展示清晰度和创新性同时成立。", "本项目的亮点不是单点算法，而是完整链路：DSL 可审计、AI 不越权、Doris 优化可解释、测试证据可复现、提交包可回溯。", "文档和 Demo 需要把这些亮点串成一个故事，让评委在短时间内看到问题、方案、证据和价值。"),
        ],
    ),
    (
        "产品介绍与用户价值",
        [
            ("产品定位", "产品定位", "FinDSL Forge 可以理解为面向金融筛选任务的可审计编译平台。", "业务人员或研究人员用自然语言或 DSL 表达选股逻辑，系统将其转成可在 Apache Doris 上执行的 SQL，并返回 AST、SQL、优化说明和验证结果。", "产品价值在于降低复杂 SQL 编写门槛，同时把金融系统需要的可解释性和可复现性保留下来。"),
            ("核心用户画像", "用户画像", "第一类用户是金融策略研究者，他们关心表达效率、指标组合和快速验证；第二类用户是数据工程师，他们关心 SQL 可控、Doris 兼容和性能稳定。", "第三类用户是比赛评委或技术负责人，他们不一定关心每一行代码，但关心系统是否真正解决赛题、是否有证据支持、是否具备进一步工程化可能。", "文档按这些角色组织内容，既能给业务读者看价值，也能给技术读者看实现。"),
            ("典型业务场景", "业务场景", "场景一是窗口型条件，例如近 120 日成交量累计超过阈值；场景二是连续性条件，例如连续 3 天主力净流入为正；场景三是横截面排名，例如按换手率取每日前 100。", "这些条件在真实金融筛选中常常组合出现，手写 SQL 会产生大量 CTE、窗口层、join 和排序细节。", "FinDSL Forge 将这些细节封装在确定性编译器里，让用户关注业务表达，让系统负责正确生成和验证。"),
            ("与普通文本转 SQL 的区别", "差异化", "普通文本转 SQL 方案容易把模型生成的 SQL 直接交给数据库，短期看演示快，长期看风险大。", "本项目的 AI 层只允许输出 DSL 候选，候选必须通过 parser、semantic analyzer、SQL generator、Doris SQL validator 和 reference equivalence。", "这种设计牺牲了一点自由度，却换来金融场景更重要的可审计、可诊断和可复现。"),
        ],
    ),
    (
        "系统总体架构",
        [
            ("分层架构概览", "系统架构", "系统从上到下分为输入层、编译层、验证层、执行层和展示层。", "输入层接收 DSL、中文自然语言或 LLM 候选；编译层负责词法、语法、AST、语义和 SQL 生成；验证层负责参考语义、SQLite 回归和 Doris SQL 安全检查。", "执行层面向 Apache Doris，展示层通过 Web Demo、Markdown 报告和 Word 文档服务于竞赛提交。"),
            ("模块协作方式", "模块协作", "模块之间采用明确的输入输出边界，Compiler 返回 SQL、AST、trace 和 explain，ReferenceEvaluator 返回基准结果键，EquivalenceVerifier 比较两边结果。", "这种接口划分使得每个模块都能单独测试，也便于在未来替换 Doris 集群、扩展指标表或接入真实 LLM provider。", "从竞赛角度看，清晰模块边界也使答辩更容易展开：每个得分点都能对应到一个模块和一份证据。"),
            ("证据链架构", "证据链", "系统不是等到最后才写报告，而是把证据生成纳入工程流程。", "official suite、evaluation report、Doris evidence、defense package 和 submission readiness 都由脚本生成，最终再通过 export_submission_artifacts 进入版本化提交包。", "这种方式避免了手工截图和口头说明不一致的问题，也让每次提交都可以回答：当前状态是否真的可交付。"),
            ("架构可扩展性", "扩展性", "当前系统已经将指标、表、函数注册放在 configs 中，新增普通指标不需要改编译器核心。", "如果未来需要接入更多行情、财务、公告或情绪指标，可以先扩展 registry，再补充 official-style case 和 reference evaluator 支持。", "这种可扩展性体现为低成本业务扩展，而不是在编译器中堆叠越来越多的硬编码分支。"),
        ],
    ),
    (
        "DSL 语言设计",
        [
            ("语言设计原则", "DSL 设计", "FinDSL 的语言设计遵循三个原则：表达金融筛选语义、限制危险自由度、便于编译到 Doris SQL。", "因此 DSL 提供 filter、then、rank 等关系算子，也提供 MA、SUM、MAX、MIN、RET、CONS、EXIST 等窗口与布尔算子。", "它不像通用 SQL 那样允许任意语句，而是把金融筛选常见结构固化为可验证的语法树。"),
            ("关系算子", "关系算子", "filter 表示对股票日期关系进行筛选，then 表示多个阶段按顺序组合，rank 表示在每个交易日横截面内排序并截断。", "这些算子覆盖了绝大多数选股表达式的主结构，例如先筛 A 股，再计算窗口指标，再按换手率排名。", "关系算子输出仍然是关系，因此可以继续进入下一阶段，形成可解释的 CTE pipeline。"),
            ("窗口与聚合算子", "窗口算子", "MA、SUM、MAX、MIN 产生数值窗口特征，RET 产生基于 LAG 的区间收益率特征，CONS 和 EXIST 产生滚动布尔特征。", "编译器不会把窗口函数直接塞进 WHERE，而是先在 feature layer 中物化，再在外层 WHERE 过滤。", "这样做既符合 SQL 引擎限制，也避免嵌套窗口造成不可控计划。"),
            ("排名语义", "排名语义", "rank 支持 top、bottom 和 percent 三种截断方式，并要求 top 与 desc、bottom 与 asc 语义一致。", "这个限制看似严格，但可以避免“前 N”在低价、高价、高换手、低波动等场景下被误解。", "排序中加入 ts_code 作为稳定 tie-breaker，保证相同指标值下结果可复现。"),
            ("日期语义", "日期语义", "date_between 被编译成 trade_date 范围条件，并根据是否依赖窗口采用不同下推策略。", "非窗口条件可以完整下推，窗口条件只能安全地下推上界，prefix-sum 情况则可以在当前行扫描中保留完整范围，同时通过 row_no 找历史前缀。", "这部分是项目比较关键的语义点，因为错误日期裁剪会直接改变滚动窗口结果。"),
        ],
    ),
    (
        "编译器前端与语义分析",
        [
            ("词法分析", "Lexer", "Lexer 负责把 DSL 文本切分为标识符、字符串、数字、运算符、括号和命名参数等 token。", "它需要处理中文用户经常混用的数字、大小写和字符串边界，也要在词法阶段发现未闭合字符串、非法数字等问题。", "词法错误越早暴露，用户越容易得到可修复的诊断。"),
            ("语法分析", "Parser", "Parser 将 token 流转换为 AST，并保留函数调用、比较表达式、二元布尔表达式、命名参数等结构。", "AST 是后续语义分析和 SQL 生成的共同输入，因此不能只保留字符串片段。", "标准化 AST 还可以在 Web Demo 中展示，使评委看到系统确实完成了语言层抽象。"),
            ("语义分析", "Semantic", "语义分析检查函数参数数量、窗口是否为正整数、rank 参数是否互斥、指标是否存在、filter 条件是否为布尔表达式。", "如果 DSL 顶层不是关系或布尔筛选，或者试图用裸字段绕过 indicator 函数，系统会在 SQL 生成前失败。", "这部分是金融可审计系统的安全边界，不能依赖数据库报错兜底。"),
            ("配置注册表", "Registry", "Registry 将指标、物理表、列名、前缀表和函数元数据集中管理。", "指标大小写容错、市场代码标准化、prefix-sum 支持都基于 registry 的结构化配置实现。", "这种设计让项目具备可扩展性：新增 alpha_score 一类普通指标时，可以通过配置完成，而不是修改核心编译器。"),
        ],
    ),
    (
        "Doris SQL 生成与安全边界",
        [
            ("SQL 生成流程", "SQL 生成", "SQL 生成器以 AST 和语义类型为输入，按关系阶段、特征层、窗口层、排序层和最终过滤层逐步构造 SQL。", "它不是简单模板拼接，而是根据表达式依赖决定是否需要 join、window feature、rolling boolean 或 prefix-sum rewrite。", "最终 SQL 同时返回 trace 和 explain，使每个重要 rewrite 都能被报告和 Demo 展示。"),
            ("特征物化层", "Feature Layer", "窗口函数不能直接出现在 WHERE 中，因此编译器先生成包含窗口特征的内层 SELECT，再用外层 WHERE 过滤。", "例如 close > MA(close, 3) 会先生成 AVG(close) OVER，再在外层比较 close 和 __win_1。", "这个结构让生成 SQL 更接近生产可运行 SQL，也让 reference equivalence 能稳定验证。"),
            ("多表 join 策略", "Join 策略", "daily_quote 是股票日期骨架，money_flow 和 stock_universe 作为辅助表通过 ts_code、trade_date join。", "对资金流这类稀疏辅助表，系统使用 LEFT JOIN 保持股票日期全集，避免因为辅助数据缺失而改变筛选宇宙。", "这个设计在金融数据中很重要，因为不同数据源的覆盖范围常常不一致。"),
            ("Doris SQL Validator", "安全边界", "生成 SQL 后系统会检查单语句形态、禁止 DDL/DML token、检查已知表引用、避免窗口函数泄漏到 WHERE。", "字符串字面量会被转义，市场值中包含引号或 SQL 片段也不会变成 SQL 注入。", "成功验证会进入 DORIS_SQL_VALIDATION explain 记录，这给安全边界提供了可展示证据。"),
            ("Doris 兼容性", "Doris 兼容", "项目面向 Doris 的 MySQL 兼容查询端口，生成 SQL 避免依赖本地 SQLite 独有语法。", "Doris 侧使用自动分区、hash 分桶、colocate group 和 prefix table 来支撑查询执行。", "本地 SQLite 只作为快速回归执行器，不被用作 Doris 性能结论。"),
        ],
    ),
    (
        "性能优化算法与实验设计",
        [
            ("长窗口瓶颈", "性能瓶颈", "金融筛选常常需要 60 日、120 日、250 日窗口，直接使用窗口函数会对每个股票日期重复计算历史区间。", "在大规模行情数据中，这类窗口计算容易成为主要耗时来源，尤其当查询只需要判断阈值而不需要完整窗口明细时。", "赛题要求 10x 级长范围加速，因此必须设计可解释、可验证的优化路径。"),
            ("前缀和优化原理", "Prefix Sum", "对于滚动 SUM，可以预先维护同一股票按交易日排序的累计和。", "窗口和等于当前行前缀值减去 row_no 减 N 的历史前缀值，即 window_sum(i,N)=prefix(i)-prefix(i-N)。", "这把每行 N 次累加转化为两次查找和一次减法，理论上适合长窗口。"),
            ("热点窗口物化列", "Hot Window", "为了进一步降低查询时 prefix 自连接成本，项目为 volume 的 120 日窗口配置了 volume_sum_120 热点物化列。", "在最终 5M Doris 证据中，优化 SQL 可以直接读取 dwd_stock_daily_quote_prefix 中的 volume_sum_120，并把阈值过滤下推到 prefix 表扫描。", "这使 EXPLAIN 中能清楚看到 prefix table 和谓词位置，便于评委理解优化效果。"),
            ("日期裁剪与分区剪枝", "日期裁剪", "Doris 表按 trade_date 自动分区，date_between 语义可以帮助减少扫描范围。", "但窗口查询不能简单下推下界，否则会丢失窗口历史，因此系统区分普通过滤、窗口过滤和 prefix-sum 过滤三种情况。", "这种细粒度裁剪保证正确性优先，再在安全范围内获取分区剪枝收益。"),
            ("Doris 证据设计", "实验证据", "Doris 规模实验加载 5,000,000 行 daily_quote 数据，分别执行 baseline window SQL 和 optimized prefix SQL。", "证据报告记录行数一致、baseline 平均 5182.042 ms、optimized 平均 142.993 ms、集群加速 36.24x。", "由于采集时禁用 SQL cache，这个结果不是缓存命中造成的假加速。"),
        ],
    ),
    (
        "AI 大模型辅助与安全设计",
        [
            ("AI 辅助定位", "AI 辅助", "项目利用 AI 的方式是降低输入门槛，而不是让模型直接控制数据库。", "中文自然语言会先通过 NL2DSL 模板层生成候选 DSL，然后候选进入同一条确定性编译、验证和执行链路。", "这使 AI 成为业务表达助手，而不是不可审计的 SQL 生成器。"),
            ("NL2DSL 模板层", "NL2DSL", "模板层覆盖连续主力净流入、低价 bottom 排名、换手率百分比、B 股均量阈值、日期区间均线、滚动最小值、日期前缀和等官方风格表达。", "系统还支持斜杠日期、中文年月日、近半年等真实用户常见写法。", "候选 DSL 会带有 rule、confidence 和 rationale，方便在 Demo 中解释为什么这样翻译。"),
            ("LLM 候选安全环", "LLM Safety", "LLM adapter 可以解析 JSON 或 markdown 风格的模型响应，但会把直接 SQL 输出识别为 UNSAFE_DIRECT_SQL。", "剩余 DSL 候选还要经过编译、Doris SQL validation 和 reference equivalence。", "因此即使未来接入真实模型 provider，也不会改变核心安全约束。"),
            ("诊断与修复建议", "诊断", "错误 DSL 不会只返回 traceback，而是返回稳定 diagnostic code 和修复建议。", "例如 indicator(\"clos\") 会触发 UNKNOWN_INDICATOR，并建议 indicator(\"close\")。", "这让系统不仅适合比赛演示，也适合真实用户迭代表达式。"),
        ],
    ),
    (
        "数据模型、Doris 部署与环境操作",
        [
            ("逻辑数据模型", "数据模型", "系统当前使用 daily_quote、money_flow 和 stock_universe 三类表。", "daily_quote 包含 ts_code、trade_date、close、turnover_rate、volume，是核心股票日期骨架；money_flow 包含 main_net_inflow；stock_universe 提供市场类型。", "这种最小模型足以覆盖赛题关键语义，也便于后续扩展到更多指标。"),
            ("Doris 表设计", "Doris 表设计", "Doris schema 使用 monthly trade_date auto partition 和 ts_code hash distribution。", "基础表和 prefix 表共享 colocate group，使同一股票维度的 join 更容易保持局部分布。", "这些物理设计不是装饰，而是为了支撑日期裁剪和 prefix table join 的执行效率。"),
            ("本地 Docker 环境", "部署环境", "项目提供 deploy/doris/docker-compose.quickstart.yaml，适配 Windows Docker Desktop 的低内存运行方式。", "FE 和 BE 的 JVM 与内存参数已经调低，适合本机比赛开发和证据采集。", "正式生产环境仍应提高 replication_num、bucket 数和 BE 数量。"),
            ("Stream Load 流程", "数据导入", "小样本可以通过 02_sample_data.sql 插入，5M 规模数据必须使用 Doris Stream Load。", "prepare_doris_scale_evidence.ps1 会生成 deterministic CSV、应用 schema、清空旧表、Stream Load 三张基础表、重建 prefix 表并采集证据。", "这条脚本把原本容易出错的手工过程变成可复现流程。"),
            ("真实数据接入", "真实数据", "合成数据用于可复现实验，真实数据用于增强业务可信度。", "真实行情只需保持 ts_code、trade_date、close、turnover_rate、volume、main_net_inflow、market 等字段一致，即可进入相同 Doris schema。", "答辩时应明确区分真实样例和合成性能基准，避免把数据来源混为一谈。"),
        ],
    ),
    (
        "功能操作指南",
        [
            ("安装与基础检查", "基础操作", "使用项目时先确认 Python、Docker Desktop、WSL2、MySQL client 和 Git 均可用。", "普通编译和测试不依赖 Doris，只有采集真实 Doris 规模证据时才需要 Docker Doris 集群。", "如果 Docker 镜像拉取受网络影响，可以在脚本中使用 -ProxyUrl 指向本地 VPN 代理。"),
            ("CLI 编译操作", "CLI", "最基本的操作是调用 python -m findsl.cli compile 加 DSL 文本。", "输出可以是 SQL，也可以加 --json 查看 AST、trace、explain 和 elapsed_ms。", "建议答辩前准备三条 CLI 示例：普通过滤、窗口查询、prefix-sum 查询。"),
            ("诊断操作", "诊断操作", "当表达式非法时，可以使用 diagnose 命令查看错误码和修复建议。", "这比只看 Python 异常更适合展示工程成熟度，因为真实用户需要知道如何修复输入。", "负例套件中已经覆盖未知指标、非法窗口、非法 rank、非法日期、裸字段绕过等场景。"),
            ("Web Demo 操作", "Web Demo", "serve_demo.ps1 会启动本地 Web Demo，默认端口为 8765。", "页面提供自然语言输入、DSL 输入、样例选择、SQL/AST/Explain/Rows/Evidence 标签和 Copy SQL 按钮。", "推荐现场演示时先跑默认中文需求，再选择 prefix-sum 正例和 UNKNOWN_INDICATOR 负例。"),
            ("Readiness 操作", "Readiness", "submission_readiness.ps1 是提交前总验收入口。", "它会运行 pytest、evaluation、equivalence、benchmark、official suite、defense package、Doris evidence marker 和 git cleanliness。", "最终报告中 Blocking gates passed 为 True 且 Warning count 为 0 时，项目才进入可提交状态。"),
        ],
    ),
    (
        "测试、验证与质量保障",
        [
            ("单元测试体系", "测试体系", "项目测试覆盖 parser、compiler、semantic、diagnostics、nl2dsl、llm_adapter、doris_sql、doris_evidence、demo 和 readiness。", "当前全量 pytest 结果为 169 passed，这说明新增收益率算子和文档增强没有破坏核心链路。", "测试数量不是目的，关键是每个高风险行为都有对应断言。"),
            ("官方风格覆盖套件", "官方套件", "official_positive_cases.jsonl 和 official_negative_cases.jsonl 构成比赛风格回归语料。", "正例要求编译成功、SQL 片段匹配、trace 片段匹配、explain 规则匹配，并且 SQL/reference 等价。", "负例要求失败方式可控，返回预期 diagnostic code 和可操作建议。"),
            ("语义等价验证", "等价验证", "Pandas reference evaluator 直接解释 DSL，SQLite executor 执行编译生成 SQL。", "两者结果按 ts_code、trade_date 键比较，发现 missing 或 extra 即视为语义错误。", "这种双路径验证降低了 SQL 生成器自证正确的风险。"),
            ("Doris 规模验证", "Doris 验证", "Doris evidence collector 在真实 MySQL 兼容端口上执行 EXPLAIN 和 COUNT(*)。", "baseline 与 optimized 必须都成功、行数必须一致、baseline plan 必须包含 window、optimized plan 必须包含 prefix table、加速必须超过阈值。", "任一条件不满足都不应在答辩中宣称性能达标。"),
            ("提交包证据", "提交包", "reports 目录是本地生成目录，默认不进入 Git。", "export_submission_artifacts.ps1 会把轻量报告复制到 submission_artifacts/evidence_snapshots，形成可版本化证据快照。", "这样既避免提交数百 MB 数据，又能保证评审看到与代码版本对应的证据。"),
        ],
    ),
    (
        "竞赛答辩与材料组织",
        [
            ("答辩主线", "答辩主线", "建议答辩从问题出发：金融筛选表达复杂、手写 SQL 维护困难、LLM 直接生成 SQL 风险高、长窗口查询性能差。", "随后展示方案：DSL 编译器、确定性验证、Doris prefix-sum 优化和 AI 候选安全环。", "最后用 readiness 和 Doris evidence 证明结果，而不是只展示界面。"),
            ("演示节奏", "演示节奏", "五分钟演示可以按自然语言输入、候选 DSL、SQL/AST、prefix-sum 正例、负例诊断、Doris 证据、readiness 报告顺序进行。", "这个顺序让评委逐步看到输入友好、编译严谨、优化有效、错误可控、证据完整。", "如果现场 Doris 容器不可用，就展示 evidence snapshots 中已经版本化的 Doris 证据。"),
            ("PPT 组织", "PPT 组织", "PPT 不宜堆代码，应围绕痛点、方案、架构、DSL 能力、正确性、性能证据、AI 安全、工程化和创新点展开。", "每页只讲一个核心结论，并用证据文件名或截图支撑。", "答辩时可以把本文档作为完整资料，PPT 作为高密度讲解提纲。"),
            ("得分点映射", "得分点", "score_mapping.md 已经把 DSL、语义、Doris SQL、复杂算子、正确性、性能、AI、安全和工程交付映射到实现与证据。", "在答辩时应主动告诉评委：每个赛题要求都有对应模块、测试和报告，而不是赛后整理。", "这种映射能减少评委追问时的模糊回答，提高项目可信度。"),
        ],
    ),
    (
        "工程管理、Git 回溯与风险控制",
        [
            ("Git 工作流", "Git", "项目使用 main 分支持续提交，每次关键功能完成后运行测试和 readiness，再 commit、push、生成 bundle 备份。", "这种流程保证即使本机环境变化，也能通过 GitHub 或 bundle 回到可用版本。", "竞赛项目越接近提交阶段，越不能依赖未提交的本地状态。"),
            ("Bundle 备份", "备份", "Git bundle 是离线回溯手段，适合在网络不稳定或远端不可访问时保留完整仓库历史。", "当前备份目录位于研究生金融科技创新大赛/git_bundles。", "每次重要提交后生成新的 bundle，可以降低误操作和环境损坏风险。"),
            ("风险清单", "风险控制", "剩余风险主要包括真实行情样例不足、最终答辩视频仍需录制、真实 LLM provider 未接入、多 BE 生产 Doris 未实测。", "这些风险不影响当前核心赛题完成度；Web Demo 截图已经进入提交包，后续重点是把截图和报告组织成清晰讲解。", "文档中应诚实区分已完成证据、可选增强和未来扩展，避免过度承诺。"),
            ("质量门禁", "质量门禁", "团队开发时应把 pytest、official-suite、submission-readiness 作为三层门禁。", "小改动至少跑相关测试，大改动必须跑全量 readiness；涉及性能或 Doris schema 的改动必须重采 Doris evidence。", "质量门禁的价值在于把主观感觉转化为可复核结果。"),
        ],
    ),
    (
        "后续增强路线",
        [
            ("真实数据样本", "真实数据增强", "下一步可以接入一份真实或公开行情样本，规模不需要特别大，重点是证明字段、语义和业务场景真实。", "真实样本可以用于 Demo 展示，合成 5M 数据继续作为可复现性能基准。", "二者分工清楚，既能增强业务可信度，又不会牺牲实验可复现性。"),
            ("多节点 Doris", "多节点 Doris", "当前本地环境是单 FE/BE Docker Desktop，已经足够完成赛题证据。", "如果继续提升企业级交付，可以搭建多 BE 集群，测试 replication_num、bucket、colocate group 和 Stream Load 并发写入。", "多节点实测能进一步证明系统不是只适合本机演示。"),
            ("物化视图与增量维护", "物化视图", "prefix table 当前通过重建脚本生成，适合比赛复现。", "生产系统可以研究 Doris materialized view 或定时增量任务维护热点窗口指标。", "这样可以把离线构建成本转化为持续更新机制，更贴近实际投研平台。"),
            ("真实 LLM Provider", "LLM Provider", "可选增强是接入真实 OpenAI 或国产大模型 provider。", "但接入后仍必须保持“模型只提 DSL 候选，系统负责验证”的架构约束。", "如果模型输出不稳定，安全环应拒绝而不是放宽 SQL 执行边界。"),
            ("更多 DSL 算子", "DSL 扩展", "当前已补齐 RET 区间收益率；未来仍可扩展波动率、成交额、行业中性、公告情绪、财务因子等指标。", "扩展时应遵循配置优先、参考语义先行、official case 同步增加的原则。", "不要为了快速增加功能而破坏编译器核心的可审计性。"),
        ],
    ),
]


APPENDIX_SECTIONS = [
    (
        "常用命令速查",
        [
            "启动 Demo、运行 readiness、导出 artifacts、采集 Doris 证据是提交阶段最常用的四类操作。",
            "如果只做普通开发，优先运行 pytest 和 official-suite；如果涉及 Doris 性能路径，必须重跑 collect-doris-evidence 或 prepare_doris_scale_evidence。",
        ],
    ),
    (
        "术语表",
        [
            "DSL 指领域特定语言，在本项目中用于表达金融筛选逻辑。",
            "AST 指抽象语法树，是编译器前端输出的结构化表示。",
            "Prefix-sum 指前缀和优化，用累计值差分计算滚动窗口和。",
            "Readiness 指提交前总验收报告，整合测试、性能、证据和 Git 状态。",
        ],
    ),
    (
        "最终提交建议",
        [
            "提交前请确保 GitHub 已 push，bundle 已生成，submission_artifacts 中证据快照与代码版本一致。",
            "答辩现场请准备 Web Demo、Doris 证据文件、readiness 报告、PPT 和一份离线 Word 文档。",
        ],
    ),
    (
        "提交前检查清单",
        [
            "第一项检查代码状态。运行 `git status --short`，确认只有本次需要提交的文件处于修改状态；如果存在临时渲染图、PDF 预览、缓存目录或大规模数据文件，应在提交前移除或确认 `.gitignore` 已覆盖。竞赛提交最怕把本地临时文件混入仓库，既影响评审观感，也增加后续回溯难度。",
            "第二项检查测试状态。至少运行 `python -m pytest -q`，涉及 DSL、SQL、诊断、Demo 或 Doris evidence 的改动，还要运行 official-suite、defense-package 和 submission-readiness。测试结果应记录在最新 readiness 或终端日志中，不能只凭上一次通过的印象判断当前版本可用。",
            "第三项检查证据快照。`submission_artifacts/evidence_snapshots` 中的 reports 应与当前代码版本匹配，尤其是 Doris evidence、official suite 和 readiness。若刚刚重跑过 Doris 证据或修改过文档引用，需要重新执行 `scripts/export_submission_artifacts.ps1`，让提交包同步更新。",
            "第四项检查 Word 文档。打开 `docs/FinDSL_Forge_中文综合操作指南.docx`，确认目录章节完整、中文字体正常、表格没有越界、页眉页脚没有异常。文档是评审最容易直接打开的材料之一，版式问题会直接影响专业感。",
            "第五项检查演示入口。确认 `scripts/serve_demo.ps1` 能启动，浏览器能访问 `http://127.0.0.1:8765`，默认样例、中文建议、SQL 标签、AST 标签、Evidence 标签和负例诊断都能工作。若现场不准备实时 Doris，则提前打开 evidence snapshot 作为备用材料。",
            "第六项检查 GitHub 与 bundle。push 成功后生成新的 bundle，文件名带时间戳，放在 `git_bundles` 目录。远端仓库和离线 bundle 同时存在，才算完成可回溯备份。提交前最好记录最新 commit hash，便于团队成员之间确认版本一致。",
            "第七项检查材料口径。PPT、Word 手册、README 和答辩讲稿中的关键数字要一致：169 passed、32/32、34/34、5,000,000 行、36.24x、warning count 0。任何一个数字更新，都要同步到所有材料，避免评委发现前后矛盾。",
            "第八项检查风险表述。真实 LLM provider、多节点 Doris、更多真实数据样本等内容应写成后续增强或可选冲刺项；已经完成的内容则要能给出文件和命令。诚实区分状态，比把规划写成成果更安全。",
        ],
    ),
    (
        "现场答辩备用方案",
        [
            "如果现场网络不可用，优先使用本地 Demo、已生成的 Word 手册、PPT 和 evidence snapshots。Doris 镜像拉取、GitHub 访问和在线模型调用都不应成为现场演示的必要条件。比赛答辩要保证核心链路在离线状态下仍能讲清楚。",
            "如果 Docker Doris 未能启动，不要把时间耗在现场排查容器。可以说明 Doris 规模证据已提前采集并版本化，现场 Demo 使用本地样本验证语义，性能结论来自 `submission_artifacts/evidence_snapshots` 中的 Doris evidence。这个备用说法要提前排练，避免临场显得慌乱。",
            "如果 Web Demo 端口被占用，改用 CLI 演示。准备好三条命令：一个中文 suggest-dsl 示例，一个 prefix-sum compile 或 verify-sql 示例，一个 diagnose 负例。CLI 虽然不如界面直观，但能证明后端能力仍然可用。",
            "如果评委追问为什么不用大模型直接生成 SQL，回答应聚焦金融安全：模型可以帮助生成候选 DSL，但 SQL 执行必须经过 parser、semantic analyzer、SQL generator、validator 和 reference equivalence。这样既利用 AI，又不把数据库安全交给不可控输出。",
            "如果评委追问 36.24x 是否适用于全部查询，应明确说明这是 5M 数据、120 日成交量滚动 SUM、prefix 热点列路径上的结果。其他查询会根据函数、指标和窗口条件选择不同路径，项目不会把单一路径的加速泛化到所有场景。",
            "如果评委追问真实数据，回答应区分数据用途：合成数据负责可复现规模性能，真实样本可用于增强业务展示。当前核心赛题证明不依赖私有真实行情，但后续可按相同 schema 接入公开或授权数据。",
            "如果时间只剩最后一分钟，优先讲三句话：系统把金融筛选表达编译为 Doris SQL；正确性由 reference equivalence 和官方风格套件证明；性能由 5M Doris evidence 证明，并已达到 36.24x 长窗口加速。不要在最后阶段打开新页面或新命令。",
        ],
    ),
    (
        "常见问题与处理建议",
        [
            "问题一：`mysql.exe` 找不到。先确认 MySQL client 安装目录是否加入 PATH，重新打开 PowerShell 后运行 `mysql --version`。连接 Doris 只需要客户端，不需要安装 MySQL Server；如果端口是 9030，目标服务是 Doris FE 的 MySQL 协议接口。",
            "问题二：Docker 拉取 Doris 镜像失败。先确认 VPN 或代理是否可用，再使用脚本中的 `-ProxyUrl \"http://127.0.0.1:7897\"` 参数。Docker Desktop 的代理设置和 PowerShell 环境变量可能不完全一致，必要时分别检查。",
            "问题三：Doris 容器启动后连接失败。检查容器是否健康、FE 是否监听 9030、端口是否被占用、Windows 防火墙是否拦截。不要急着改 SQL，连接层问题和查询层问题要分开排查。",
            "问题四：Stream Load 失败。优先看 Doris 返回的 JSON 结果，其中通常包含错误行数、列匹配问题或权限信息。然后检查 CSV 分隔符、列顺序、表名、数据库名和 schema 是否与脚本一致。",
            "问题五：pytest 通过但 readiness 失败。readiness 包含更多门禁，可能是 artifacts 未导出、Doris evidence marker 缺失、official suite 失败或 Git 状态不干净。应按报告中的失败项处理，而不是只重新跑 pytest。",
            "问题六：Web Demo 显示负例失败。先查看 API 返回的 diagnostic code 是否变化，再检查 official negative cases。负例不是简单“报错”，而是要求返回预期错误码；如果错误码变了，说明诊断契约可能被破坏。",
            "问题七：Word 文档生成后字符数不足。运行 `scripts/build_chinese_manual_docx.py` 会输出 Markdown 中文字符数。若低于 3 万，应补充真实内容，例如操作细节、答辩备用方案、算法边界和风险说明，而不是复制模板句式。",
            "问题八：Git push 受网络影响。使用本地代理执行 push，并在成功后立即生成 bundle。若远端短时不可用，bundle 可以保证本机已有完整历史；网络恢复后再补 push。",
        ],
    ),
    (
        "中文文档自然化审校标准",
        [
            "审校时首先看句式开头。如果连续小节都使用同一类“按视角分段”的固定开场，或者每段都先套一句场景说明，就说明正文仍有模板痕迹。合格文档应根据内容自然起句，有的从问题开始，有的从结论开始，有的从操作场景开始。",
            "其次检查空泛形容词。诸如“高效、智能、先进、全面、强大”如果没有证据支撑，就应替换成具体事实。比如不要只写“性能优秀”，而要写“5M Doris 实验中 baseline 平均 5182.042 ms、optimized 平均 142.993 ms”。",
            "第三检查段落功能。每个段落最好承担一个明确任务：解释判断、描述实现、说明操作、提示风险或给出证据。如果一段话只是反复强调项目很好，却没有增加新信息，就应该删掉或重写。",
            "第四检查术语一致。DSL、AST、semantic analyzer、Doris SQL validator、reference equivalence、readiness 等术语要保持稳定，不要在不同章节随意换说法。自然写作不等于随意写作，企业文档更需要统一口径。",
            "第五检查“不是……而是……”的使用频率。这个句式偶尔能澄清边界，但用多了会显得像模板说明。能直接陈述的地方就直接陈述，例如“AI 只生成 DSL 候选，后续由编译链路验证”，比反复对比更自然。",
            "第六检查表格是否承担了合适任务。表格适合映射、清单和证据摘要，不适合塞入大段解释。若表格单元里都是长段文字，应改成正文段落；若正文里全是命令和数字，则可以改成表格提高可读性。",
            "第七检查文档是否诚实。已完成的内容要给出文件、脚本和结果；未完成的内容要放进风险或规划。企业级文档不靠夸张语气建立信任，而靠边界清楚、证据充分和复现路径明确建立信任。",
            "第八检查朗读效果。把关键章节快速读一遍，如果每段节奏几乎相同，或者大量句子像“该模块用于……该模块能够……该模块支持……”，就需要重写。自然文档应有长短变化和真实判断，读起来像工程负责人写给评审和团队的材料。",
        ],
    ),
    (
        "国家级奖项冲刺验收重点",
        [
            "冲刺阶段的第一目标是把核心链路讲得足够硬。当前项目已经有 DSL、编译器、Doris SQL、reference equivalence、prefix-sum 和 readiness，这些内容构成主干。最后几天不宜盲目增加大功能，除非新增内容能明确提升评委对主干能力的判断。",
            "第二目标是增强真实感。真实感不等于接入庞大真实数据，而是让作品在操作、文档和演示上像一个可交付系统。清楚的启动脚本、稳定的 Demo、完整的 Word 手册、可回溯 Git 历史和离线证据，都能让评委感到团队做的是工程作品。",
            "第三目标是让亮点集中。答辩材料里应反复强化四个亮点：受限 DSL 保证金融表达可控，AI 安全环防止模型越权，prefix-sum 和热点窗口实现 Doris 长窗口加速，readiness 与 artifacts 保证提交可复核。亮点太散，反而会削弱记忆点。",
            "第四目标是准备追问。每个核心结论都要有下一层解释：为什么要用 DSL，为什么要 reference evaluator，为什么要 prefix table，为什么 SQLite 不能替代 Doris，为什么 36.24x 不能泛化到所有查询。提前准备这些回答，现场会稳很多。",
            "第五目标是清理材料。README 负责快速理解，Word 手册负责深度说明，PPT 负责现场表达，submission_artifacts 负责证据复核，git_bundles 负责离线备份。每份材料都有角色，不要让同一份文件承担所有功能。",
            "第六目标是控制风险。真实 LLM provider、多节点 Doris 和更多 DSL 算子都值得做，但如果它们在截止前无法形成稳定证据，就不要放进主演示流程。可选增强可以写进规划，主流程必须围绕已经验证的能力。",
            "第七目标是统一语言。团队成员在答辩中要使用同一套术语：候选 DSL、确定性编译链路、reference equivalence、Doris evidence、submission readiness。术语一致能显著减少评委听感上的混乱。",
            "第八目标是保留演示余量。现场不要把所有时间押在容器启动、镜像拉取或实时重采 5M 证据上。最稳妥的方式是现场展示 Demo 和快照，复现脚本作为可查证能力说明。比赛评审看的是作品能力，不是现场运维表演。",
            "第九目标是强化边界表达。项目已经完成的内容要讲得有底气，暂未完成的内容要讲得诚实。比如真实 provider 未接入，不影响离线安全环成立；多节点 Doris 未实测，不影响单节点 Doris 规模证据成立。边界清楚，反而更专业。",
            "第十目标是保持仓库干净。最终提交前不要出现未追踪的大文件、临时预览 PDF、渲染图片目录、Docker 中间数据或个人环境配置。一个干净仓库会让评委和后续维护者更容易复核，也降低误提交风险。",
            "第十一目标是把性能证据讲完整。36.24x 的价值不只在数字，而在实验设计：同一 DSL、两条 SQL、行数一致、SQL cache 禁用、baseline window、optimized prefix table、真实 Doris 执行。把这些条件讲清楚，数字才有可信度。",
            "第十二目标是让文档和代码同步。若最后修改了脚本、证据或 README，就要重新生成 Word 和 Markdown；若修改了核心代码，就要重新跑测试；若修改了 Doris 路径，就要重采 evidence 或明确说明未重采。同步纪律是顶级交付的底线。",
        ],
    ),
    (
        "交付物目录说明",
        [
            "`src/findsl` 是项目核心代码目录，包含 lexer、parser、semantic、sqlgen、reference、doris evidence、nl2dsl、llm adapter 和 demo 相关模块。评委如果需要看实现，应优先从这里理解系统结构，而不是从脚本入口倒推。",
            "`configs` 保存指标和函数相关配置，是扩展能力的重要位置。新增指标时，应先考虑配置是否能表达，再判断是否需要修改核心代码。这个目录体现了项目把业务元数据从编译器逻辑中分离出来的设计。",
            "`data/samples` 保存本地样例数据和候选响应。它适合快速跑 reference、verify-sql、suggest-dsl 和 validate-llm-candidates。样例数据规模不大，目标是语义验证和演示，而不是性能证明。",
            "`deploy/doris` 保存 Doris schema、sample data、prefix table build 和 smoke query 资产。这个目录证明项目不只生成 SQL 字符串，也考虑了目标数据库的表结构、分区、分桶和前缀表设计。",
            "`scripts` 保存操作入口。常用脚本包括 `serve_demo.ps1`、`submission_readiness.ps1`、`prepare_doris_scale_evidence.ps1`、`export_submission_artifacts.ps1` 和本文档生成脚本。答辩前应确认这些脚本路径在 README 和手册中一致。",
            "`reports` 是本地生成报告目录，适合开发和调试。由于报告可能频繁更新或包含较大内容，不应把它和提交快照混为一谈。需要版本化的轻量证据应通过 export 脚本进入 `submission_artifacts`。",
            "`submission_artifacts/evidence_snapshots` 是评审复核的重点目录。这里应保留 readiness、official suite、Doris evidence 和 defense package 等关键报告快照。它们代表当前提交版本的证据，不应随意手工改写。",
            "`docs` 保存中文手册、runbook、score mapping 和其他说明材料。Word 手册面向完整阅读，Markdown 版本便于 diff 和版本管理；两者由同一个生成脚本产出，减少内容漂移。",
            "`git_bundles` 位于比赛目录上层，用于保存离线仓库备份。bundle 文件不一定进入项目仓库，但应在本机保留。每次重要 push 后生成 bundle，是防止远端或本地误操作的低成本保险。",
            "最终交付时，团队应能说清楚每个目录的用途。目录说明看似基础，却能体现项目是否经过整理。评委打开仓库后，如果能快速找到代码、数据、脚本、文档和证据，第一印象会明显更好。",
        ],
    ),
    (
        "文档版本维护建议",
        [
            "Word 手册和 Markdown 源应始终由 `scripts/build_chinese_manual_docx.py` 统一生成。不要在 Word 中手工改正文后忘记同步脚本，也不要只改 Markdown 后忽略 DOCX。生成脚本是单一内容来源，能减少不同格式之间的漂移。",
            "每次更新核心数字后，都要全文搜索旧值。比如 pytest 数量、官方套件通过数、Doris 行数、加速比和 readiness warning 数都可能随项目变化而变化。旧数字残留会让材料显得不严谨，甚至让评委怀疑证据是否真实。",
            "新增功能时，文档应同步补三类信息：它解决什么赛题问题，如何操作或复现，证据在哪里。只写功能介绍不够，只写命令也不够；企业交付文档需要把价值、步骤和证据放在一起。",
            "删除或调整功能时，也要维护文档。比赛冲刺阶段常常会移除不稳定功能，如果文档仍然保留旧描述，现场演示时很容易被问到无法展示的内容。文档应反映当前可交付状态，而不是历史愿望。",
            "文档审校建议分两轮。第一轮看技术事实，确认模块名、路径、命令、指标和结果都正确；第二轮看表达质量，删除重复句式、空泛形容词和模板化过渡。先保真，再润色，顺序不要反。",
            "生成 DOCX 后要做视觉检查。自动脚本能保证内容一致，但不能保证分页、表格宽度、字体和页眉页脚一定完美。正式提交前应打开 Word 或渲染成 PDF 抽检首页、目录附近、长表格页、附录页和最后一页。",
            "如果多人协作，建议把文档修改也纳入 Git review。长文档最容易产生“顺手改一句”的不可追踪变化，脚本化生成和 Git diff 能让团队看到实际改了哪些段落，避免无意改坏关键表述。",
            "最终归档时，保留 DOCX、Markdown、生成脚本和对应 commit。DOCX 便于评审打开，Markdown 便于版本比较，脚本保证可再生成，commit 保证能回到当时状态。四者同时存在，文档才算真正可维护。",
        ],
    ),
    (
        "最终演练脚本",
        [
            "演练开始前，先打开 Web Demo、PPT、Word 手册和 evidence snapshot，不要把演示建立在临时查找文件上。讲解人应先用三十秒说明题目：项目把金融选股 DSL 编译为 Apache Doris SQL，并用确定性验证和 Doris 实测证明结果。",
            "第一段演示中文输入。输入一条官方风格需求，展示系统生成 DSL 候选，再切到 AST 和 SQL。这里的讲解重点不是“AI 很聪明”，而是“自然语言只能提出候选，真正执行前必须经过编译器和验证链路”。",
            "第二段演示长窗口优化。切换到 120 日成交量累计示例，展示 explain 中的 prefix 相关记录，再打开 Doris evidence 中的 baseline 与 optimized 对比。讲解时强调行数一致、SQL cache 禁用和 36.24x 加速，避免只报一个孤立数字。",
            "第三段演示负例诊断。输入未知指标或直接 SQL，展示 diagnostic code 和修复建议。这个环节要简短，但不能省略，因为它最能说明系统不是只服务成功样例，而是能处理真实用户错误。",
            "第四段展示 readiness。打开提交前报告，说明 pytest、official suite、Doris evidence、submission artifacts 和 Git 状态都被纳入检查。最后用一句话收束：项目的核心交付不是某个页面，而是一条能复现、能解释、能回溯的工程链路。",
            "演练结束后记录问题。如果某个页面加载慢、某个命令输出太长、某个解释不够顺，就立刻调整演示素材。正式答辩前至少完整走两遍，一遍按正常流程，一遍按网络或 Doris 不可用的备用流程。",
            "讲解人还要准备一句非技术版本的总结：系统把研究员说得清楚、但手写 SQL 容易出错的选股逻辑，变成数据库能稳定执行的查询，并把中间过程展示出来。这句话适合面对金融背景评委，能避免一开始就陷入编译器术语。",
            "技术追问时则切换到更具体的说法：DSL 约束输入空间，AST 保留语义结构，semantic analyzer 拦截非法表达，SQL generator 生成 Doris 查询，reference equivalence 校验结果，Doris evidence 证明长窗口性能。两套表达都要准备好。",
            "团队内部还应约定谁负责操作、谁负责讲解、谁负责补充回答。一个人同时切页面、敲命令和回答追问，容易在压力下出错。分工清楚后，即使现场节奏变化，也能保持材料、操作和讲述一致。",
            "最后一次彩排后，不再随意改动核心演示路径。若必须修改，应重新跑最小验证并更新相关材料。很多项目不是败在能力不足，而是败在最后阶段临时改动过多，导致原本稳定的演示链路被破坏。",
        ],
    ),
]


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in [("top", top), ("start", start), ("bottom", bottom), ("end", end)]:
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths: Sequence[int]) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    tbl_grid = tbl.tblGrid
    for child in list(tbl_grid):
        tbl_grid.remove(child)
    for width in widths:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(width))
        tbl_grid.append(grid_col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = Pt(widths[idx] / 20)
            tc_w = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                cell._tc.get_or_add_tcPr().append(tc_w)
            tc_w.set(qn("w:w"), str(widths[idx]))
            tc_w.set(qn("w:type"), "dxa")
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = "PAGE"
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)


def set_run_font(run, name="SimSun", size=None, bold=None, color=None) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def configure_styles(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.7)
    section.right_margin = Cm(2.4)
    section.header_distance = Cm(1.3)
    section.footer_distance = Cm(1.3)

    normal = doc.styles["Normal"]
    normal.font.name = "SimSun"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.first_line_indent = Pt(21)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.333
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for style_name, size, color, before, after in [
        ("Heading 1", 16, "2E74B5", 18, 10),
        ("Heading 2", 13, "2E74B5", 12, 6),
        ("Heading 3", 12, "1F4D78", 8, 4),
    ]:
        style = doc.styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True


def add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        set_run_font(run, "Microsoft YaHei")
    return p


def add_para(doc: Document, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Pt(21)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.333
    run = p.add_run(text)
    set_run_font(run, "SimSun", 10.5)
    return p


def add_no_indent_para(doc: Document, text: str, bold=False, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, "SimSun", 10.5, bold=bold, color=color)
    return p


def add_code_block(doc: Document, code: str):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [9360])
    cell = table.cell(0, 0)
    set_cell_shading(cell, "F4F6F9")
    p = cell.paragraphs[0]
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    for line in code.splitlines():
        run = p.add_run(line)
        run.font.name = "Consolas"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string("172026")
        p.add_run("\n")
    doc.add_paragraph()


def add_table(doc: Document, headers: Sequence[str], rows: Sequence[Sequence[str]], widths: Sequence[int]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    set_table_geometry(table, widths)
    hdr = table.rows[0].cells
    for idx, header in enumerate(headers):
        set_cell_shading(hdr[idx], "F4F6F9")
        p = hdr[idx].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Pt(0)
        run = p.add_run(header)
        set_run_font(run, "Microsoft YaHei", 9.5, bold=True, color="1F4D78")
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            p = cells[idx].paragraphs[0]
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_after = Pt(2)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx else WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(value))
            set_run_font(run, "SimSun", 9)
    set_table_geometry(table, widths)
    doc.add_paragraph()
    return table


def add_callout(doc: Document, label: str, text: str):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [9360])
    cell = table.cell(0, 0)
    set_cell_shading(cell, "E8EEF5")
    p = cell.paragraphs[0]
    p.paragraph_format.first_line_indent = Pt(0)
    run = p.add_run(f"{label}：")
    set_run_font(run, "Microsoft YaHei", 10.5, bold=True, color="1F4D78")
    run2 = p.add_run(text)
    set_run_font(run2, "SimSun", 10.5)
    doc.add_paragraph()


SECTION_PARAGRAPHS = {
    "优秀竞赛文档的共性框架": [
        "一份能支撑高水平答辩的竞赛文档，通常不是把代码功能罗列一遍。它需要先回答评委最关心的几个问题：题目到底难在哪里，方案为什么可信，结果能否复现，团队是否知道边界和风险。软件创新赛项目开发文档模板强调项目概述、设计、实现、测试和使用说明，Diataxis 把文档拆成教程、操作指南、解释和参考资料；这两类框架合起来，正好能覆盖 FinDSL Forge 的提交需求。",
        "本手册采用“技术白皮书 + 操作手册 + 证据索引”的组合结构。前半部分讲产品定位、赛题理解、系统架构和核心算法，后半部分讲部署、操作、验证、答辩与风险管理。这样的安排不是为了显得厚，而是为了让不同读者能快速找到自己的入口：评委看结论和证据，开发者看模块和命令，答辩人看主线和演示节奏。",
        "写作时参考了 Google Developer Documentation Style Guide、中文技术文档写作风格指南、openEuler、OpenHarmony 和 Apache Doris 官方文档。它们共同给出的经验很朴素：术语要稳定，步骤要能执行，结论要有证据支撑，扩展方向不能替代已经完成的内容。本手册后续所有章节都按这个标准展开。",
    ],
    "本文档的定位": [
        "本文档面向的是赛题 19 的完整交付，而不是单独的 README。README 适合快速启动项目；这份手册要把产品价值、编译器设计、Doris 执行路径、AI 辅助边界、测试证据和现场答辩方式放在同一个上下文里，方便团队在提交前统一口径，也方便评委在赛后复核。",
        "文档中的每一类结论都尽量对应到项目中的具体资产。算法说明会指向 prefix-sum rewrite、SQL generator 和 Doris evidence；操作说明会指向 `scripts/serve_demo.ps1`、`scripts/submission_readiness.ps1`、`scripts/prepare_doris_scale_evidence.ps1`；质量说明会对应 pytest、official suite、equivalence 和 readiness 报告。读者不需要相信一句空泛描述，可以顺着文件和命令查到证据。",
        "为了让文档更像企业内部交付材料，正文采用连续段落说明关键判断，表格只用于对照、清单和证据摘要。这样既保留论文式阅读的完整性，又避免把复杂问题切成一堆碎片化口号。",
    ],
    "读者对象与使用方式": [
        "评审专家通常会先判断项目是否真正击中了赛题核心，因此建议先读“赛题理解”“系统总体架构”“性能优化算法与实验设计”和“测试、验证与质量保障”。这几章能在较短时间内说明项目不是简单的文本转 SQL，而是围绕金融选股 DSL、Doris SQL 和长窗口加速建立了一条完整工程链路。",
        "开发者更适合从操作章节进入。先运行 pytest 和 official-suite，确认当前版本没有回归；再启动 Web Demo，观察 AST、SQL、Explain、Rows 与 Evidence 标签页；涉及 Doris 性能时，再按 Doris 部署章节拉起容器、导入 5M 数据并重新采集 evidence。这个顺序可以减少环境问题对理解系统的干扰。",
        "答辩人则需要把文档当作讲稿背后的材料库。现场不宜逐页讲手册，而应抽取痛点、方案、证据和亮点四条线，把每个演示动作都落到一个明确得分点上。遇到追问时，再从手册中补充细节、命令和报告位置。",
    ],
    "赛题 19 的本质问题": [
        "赛题 19 表面上是“将选股 DSL 编译为 Apache Doris SQL”，真正的难点在于三件事同时成立：表达要接近金融业务，编译要足够严格，执行要经得起规模数据验证。只把几个样例翻译成 SQL，或者让大模型直接吐出查询语句，都不足以覆盖这个题目的技术风险。",
        "金融筛选表达里常见的窗口、连续、存在、排名和日期区间，和 SQL 引擎的限制并不天然匹配。比如窗口函数不能随意放在 WHERE 中，日期下界下推可能破坏滚动窗口语义，资金流等辅助表又存在稀疏数据覆盖问题。项目把这些细节放进编译器和参考语义中处理，而不是留给演示时临场解释。",
        "项目的解题策略可以概括为：先限定 DSL 的合法表达，再把合法表达编译成 Doris 友好的 SQL，随后用独立 reference evaluator 和真实 Doris evidence 证明正确性与性能。这个路径比“多接几个输入样例”更稳，因为它直接回应了赛题中的语言设计、数据库适配和工程落地要求。",
    ],
    "核心评价指标": [
        "当前版本围绕六类指标做交付验收：编译正确率、诊断可用性、长窗口性能、Doris 兼容性、AI 辅助安全性和提交可复现性。它们分别由 official positive cases、official negative cases、Doris evidence、SQL validator、LLM candidate adapter 和 submission readiness 覆盖。",
        "已有证据里，pytest 全量回归为 169 passed；官方风格正例 32/32 通过，负例 34/34 返回预期诊断；Doris 5,000,000 行规模实验中，120 日成交量滚动窗口从 baseline 平均 5182.042 ms 优化到 142.993 ms，加速比为 36.24x。这个结果超过赛题中通常需要重点展示的 10x 级性能目标。",
        "评价指标的作用不只是写在文档里好看。每次提交前运行 readiness，团队就能知道哪些证据仍然有效、哪些结果需要重采、Git 是否处在可回溯状态。竞赛后期最怕“功能看似完成但证据散落”，这套指标体系正是为了避免这种情况。",
    ],
    "主要技术风险": [
        "这个题目的风险集中在语义、性能和展示三条线上。语义层面，窗口边界、日期裁剪、rank 方向、辅助表 join 都可能造成结果偏差；性能层面，小样本上的查询优化不能说明 Doris 大表上的真实效果；展示层面，如果演示只停留在界面按钮，评委很难判断底层系统是否扎实。",
        "项目对语义风险的处理比较克制：所有 DSL 都必须经过 lexer、parser、semantic analyzer 和 Doris SQL validator；SQL 结果还要和 Pandas reference evaluator 产生的基准结果比较。换句话说，SQL generator 不能自己给自己作证，必须接受另一条执行路径的检验。",
        "性能风险通过 Doris evidence 来压实。实验脚本生成确定性 5M 行数据，Stream Load 到 Doris，分别运行 baseline window SQL 和 optimized prefix SQL，检查行数一致、计划形态符合预期、加速比达到阈值，并在 readiness 中消费该证据。这样答辩时可以直接讨论实验设计，而不是只给出一张单独的时间截图。",
    ],
    "国家级奖项导向策略": [
        "面向国家级奖项，项目不能只证明“能跑通”。更有竞争力的交付应该让评委看到完整度：题目理解清楚，核心算法有门槛，工程实现可复现，风险边界讲得明白，演示过程能承受追问。本项目的优势恰好在于把这些要素连成了一套系统。",
        "技术亮点应重点放在四处。第一，DSL 编译链路严格限制了金融表达的合法空间；第二，AI 只产生候选 DSL，不能绕过编译器直接访问数据库；第三，prefix-sum 与热点窗口物化把长窗口查询优化成 Doris 可解释的表访问；第四，readiness 与 evidence snapshots 让提交材料和代码版本绑定。",
        "答辩策略上，不建议把项目讲成“又一个大模型应用”。更好的叙事是：大模型解决输入友好性，确定性编译器解决安全和语义，Doris 优化解决规模性能，自动化证据解决可信交付。这样的层次更符合金融科技赛题对可靠性的期待。",
    ],
    "产品定位": [
        "产品可以定位为面向金融选股任务的 DSL 编译与验证平台。用户用中文需求或受限 DSL 描述筛选逻辑，系统生成 AST、Doris SQL、优化说明、诊断结果和验证证据。它不是交易系统，也不承诺直接产生投资收益；它解决的是“如何把复杂筛选逻辑稳定、透明地落到数据仓库执行”这一工程问题。",
        "产品的直接价值在于降低 SQL 编写和维护成本。很多策略研究人员理解“近 120 日成交量累计”“连续 3 日主力净流入”“每日换手率前 100”这类金融语言，但手写 SQL 容易在窗口、排序、日期和 join 上出错。FinDSL 把这些模式固化成可检查的语言结构，让用户表达业务意图，系统承担编译和验证。",
        "对企业场景而言，另一个价值是治理边界。普通文本转 SQL 很难解释模型为什么生成某段查询，也难以保证没有危险语句；FinDSL Forge 把自由输入收束为 DSL，再由编译器输出单条安全查询。这种产品形态更适合金融机构内部的数据分析平台、投研工具和比赛评审场景。",
    ],
    "核心用户画像": [
        "第一类用户是策略研究者。他们关注指标组合速度、表达方式是否贴近业务、结果是否容易解释。对这类用户，Web Demo 的中文输入、候选 DSL、AST 和结果行预览最重要，因为它能把抽象编译链路转化为可操作体验。",
        "第二类用户是数据工程师或平台开发者。他们会关心生成 SQL 是否符合 Doris 习惯、是否会触发危险语句、能否用配置扩展指标、测试是否覆盖隐藏用例。对他们来说，代码模块、schema、脚本和 readiness 报告比界面更关键。",
        "第三类用户是评委、导师和答辩听众。他们不会逐行审查所有源码，但会通过追问判断项目是否有真实技术含量。文档需要帮助他们快速看见证据：哪些任务已完成，哪些性能指标经过真实集群验证，哪些风险被诚实标注。",
    ],
    "典型业务场景": [
        "一个常见场景是长窗口筛选，例如“筛选近 120 日成交量累计超过阈值的 A 股”。这类查询在金融数据里很常见，但直接窗口计算在大表上成本较高，也是本项目 prefix-sum 优化最能体现价值的地方。",
        "另一个场景是连续性和存在性判断。比如连续 3 天主力净流入为正，或者近几日内存在一次成交量突破。这类表达看似简单，落到 SQL 时往往需要滚动布尔聚合和窗口层。FinDSL 通过 CONS 与 EXIST 把它们作为一等语义处理。",
        "排名类场景同样重要。每日按换手率取前 100、按低价取 bottom 2、按成交额取前 50% 等需求都涉及横截面排序和稳定截断。系统为 rank 加入方向约束和 tie-breaker，避免同一批数据在不同执行环境中出现难以解释的顺序差异。",
    ],
    "与普通文本转 SQL 的区别": [
        "普通文本转 SQL 的演示往往很快：用户输入一句话，模型生成一段 SQL，数据库执行后返回结果。这个路径适合低风险查询探索，却不适合用作金融筛选系统的核心。原因很直接，SQL 是权限很高的执行语言，一旦模型理解偏差或生成危险语句，后果会被数据库放大。",
        "这里把 AI 放在更合适的位置。自然语言模块只负责提出 DSL 候选，候选必须进入 parser、semantic analyzer、SQL generator、Doris SQL validator 和 reference equivalence。任何直接 SQL、未知指标、非法窗口或不安全结构都会被拒绝，错误会返回诊断码和修复建议。",
        "这种设计牺牲了一部分自由表达，却换来了可解释边界。评委可以看到模型建议、DSL 语法树、生成 SQL、优化 trace 和验证结果，而不是只能看到一个黑盒回答。对于金融科技比赛，这比单纯追求“模型看起来聪明”更有说服力。",
    ],
    "分层架构概览": [
        "系统按职责拆成五层：输入层、编译层、验证层、执行层和展示层。输入层接收 DSL、中文自然语言或离线 LLM 响应；编译层完成词法、语法、AST、语义分析和 SQL 生成；验证层处理 Doris SQL 安全检查、SQLite 执行和 Pandas reference 对照；执行层面向 Apache Doris；展示层提供 Web Demo、报告和提交材料。",
        "这套架构的好处在于每层都有清楚的失败位置。输入不合法会在诊断阶段失败，语义不安全不会进入 SQL，SQL 形态异常不会进入 Doris，执行结果不一致会被 equivalence 捕获，提交前缺少证据会在 readiness 中暴露。问题不会被拖到最后才变成一条含糊的异常。",
        "在答辩中，可以把这张架构图作为主线反复使用。讲 AI 时，它位于输入辅助层；讲算法时，焦点转到编译和优化层；讲正确性时，指向验证层；讲性能时，再进入 Doris 执行和 evidence collector。结构稳定，听众就不容易迷失在细节里。",
    ],
    "模块协作方式": [
        "Compiler 对外返回的不只是 SQL 字符串，还包括 AST、trace、explain 和 elapsed_ms。AST 说明系统理解了输入结构，trace 记录重要 rewrite，explain 提供机器可读的优化步骤，elapsed_ms 用于观察编译开销。这些字段一起构成了前端展示和报告生成的基础。",
        "ReferenceEvaluator 与 SQL executor 是并行关系，而不是上下游关系。前者直接解释 DSL，后者执行编译产物，两边最后按 ts_code 和 trade_date 比较结果集。这样的协作方式能发现“SQL 语法正确但语义错了”的问题，特别适合窗口、日期和排名等容易出细节偏差的场景。",
        "Doris evidence collector 则负责把本地正确性扩展到真实数据库环境。它读取同一个 DSL，生成 baseline 和 optimized 两类 SQL，在 Doris 上执行 EXPLAIN 与 COUNT，并记录延迟与计划形态。模块之间保持同一套 DSL 输入，减少了人为改写实验 SQL 带来的偏差。",
    ],
    "证据链架构": [
        "项目从一开始就把证据生成放进工程流程，而不是等到提交前临时整理。pytest 负责代码级回归，official suite 负责赛题风格覆盖，equivalence 负责语义一致性，Doris evidence 负责真实集群性能，submission readiness 负责提交前总检查。",
        "证据链里比较关键的一点是可版本化。`reports` 可以存放本地生成的大量报告，但真正进入提交包的是 `submission_artifacts/evidence_snapshots` 中的轻量快照。这样既避免把大文件和临时日志塞进仓库，又能让评审看到与代码版本匹配的核心结果。",
        "这种架构对团队管理也有帮助。后续任何人改 DSL、SQL generator、Doris schema 或 Demo，都可以用同一套脚本重新生成证据，发现差异后再决定是否接受。项目状态不再依赖个人记忆，而是依赖脚本和报告。",
    ],
    "架构可扩展性": [
        "扩展性主要体现在配置、语义和执行路径三处。指标注册表把业务字段、物理表、列名、prefix 支持等信息集中起来，新增普通指标时不需要改动 parser；语义分析通过函数元数据检查参数；SQL generator 根据 registry 决定是否 join 辅助表、是否走 prefix 表。",
        "这种扩展方式对比赛很重要。隐藏用例往往不会只重复官方样例，它可能换指标、换日期、换 rank 截断方式。只要新指标符合现有语义模型，团队就能通过配置和测试扩展，而不是为每个样例写专门分支。",
        "更远的路线包括行业分类、财务因子、公告事件、情绪指标和多周期行情。无论扩展到哪类数据，都应先定义 DSL 语义，再补 reference evaluator 和 official-style case，最后才谈 Doris 物理优化。这个顺序能防止项目后期功能膨胀但质量下降。",
    ],
    "语言设计原则": [
        "FinDSL 的语言设计并不追求覆盖 SQL 的所有能力。它只保留金融筛选中高频且可验证的结构：filter、then、rank、market、date_between、indicator，以及 MA、SUM、MAX、MIN、RET、CONS、EXIST 等窗口或布尔算子。范围越明确，编译器越能给出稳定诊断和可控 SQL。",
        "语言层刻意限制了危险自由度。用户不能写任意 SELECT，不能拼接 DDL 或 DML，不能绕过 indicator 直接访问字段。所有业务指标都必须通过 registry 解析，所有函数参数都要通过语义检查。这些限制让系统更像企业平台里的安全 DSL，而不是一个松散的 SQL 生成器。",
        "语法还要照顾 Doris 编译目标。窗口函数、排名、日期范围和 prefix-sum 都会影响 SQL 结构，所以 DSL 必须让这些语义在 AST 中可识别。只有语义在树上清楚存在，后续优化器才能安全地重写。",
    ],
    "关系算子": [
        "`filter` 是最基础的关系筛选算子，它接收布尔表达式，输出仍然是股票日期关系。这个设计让条件可以继续进入 `then` 或 `rank`，形成多阶段 pipeline，而不是一次性把所有逻辑塞进一个巨大 WHERE。",
        "`then` 用来表达阶段顺序。例如先过滤 A 股，再计算连续资金流，再按换手率排名。阶段化表达对金融筛选很自然，也方便 SQL generator 生成分层 CTE。每个阶段都能保留自己的 trace，答辩时更容易解释系统做了什么。",
        "`rank` 处理每日横截面排序。它支持 top、bottom 和 percent，并且要求排序方向与截断语义一致。这个约束看上去严格，却能避免“低价 bottom”与“高价 top”被混用导致含义反转，属于金融 DSL 应该主动承担的语义保护。",
    ],
    "窗口与聚合算子": [
        "MA、SUM、MAX、MIN 负责数值窗口特征，RET 负责相对 N 个交易日前的区间收益率，CONS 和 EXIST 负责滚动布尔判断。它们的共同点是都依赖股票维度下按交易日排序的历史序列，因此 SQL 生成时必须显式处理 partition、order 和窗口边界。",
        "编译器不会把窗口函数直接放进 WHERE。正确做法是先在特征层 SELECT 中计算窗口列，再由外层查询使用这些列进行过滤。这样既符合 Doris 和多数 SQL 引擎的执行规则，也让 reference equivalence 能稳定比较生成结果。",
        "窗口算子也是项目性能优化的入口。普通窗口函数适合泛化能力，prefix-sum 适合长窗口 SUM，热点物化列适合高频比赛场景。三种路径并存，系统就能在正确性和性能之间做可解释选择。",
    ],
    "排名语义": [
        "排名问题最容易被低估。金融筛选中的“前 N”“后 N”“前百分比”往往默认按交易日分组，而不是在整个历史数据上排序。FinDSL 的 rank 明确以 trade_date 作为横截面分区，并以指标值为主排序键。",
        "为了保证结果稳定，SQL 中会加入 ts_code 作为 tie-breaker。相同指标值在真实行情中并不少见，如果没有稳定排序键，不同数据库或不同执行计划可能返回顺序不同的结果。比赛演示中这种差异会显得很不专业，因此系统在语义层提前处理。",
        "rank 参数也有诊断约束。top、bottom、percent 不能混用，方向需要匹配，百分比要落在合理范围内。负例套件覆盖这些错误，确保用户拿到的是清楚的修复提示，而不是数据库抛出的底层异常。",
    ],
    "日期语义": [
        "`date_between` 不只是一个简单的 WHERE 条件。普通字段筛选可以把上下界都下推到基础表扫描；窗口筛选如果把下界也下推，可能丢掉计算窗口所需的历史行；prefix-sum 路径又可以通过 row_no 和历史前缀表在更窄范围内完成计算。",
        "因此系统按表达式依赖区分日期处理策略。对不依赖窗口的条件，尽量下推以利用 Doris 分区剪枝；对窗口条件，保留必要历史数据；对 prefix-sum 优化，结合当前行和历史行的 row_no 关系生成安全 SQL。这个细节直接关系到结果正确性。",
        "答辩时可以把日期语义作为一个体现专业度的点来讲。很多演示型项目会把日期过滤简单套在外层，短样例看不出问题；FinDSL Forge 把窗口历史需求纳入编译规则，说明团队理解了金融时间序列查询的根本约束。",
    ],
    "词法分析": [
        "Lexer 是编译链路的第一道关口。它把输入切分成标识符、字符串、数字、运算符、括号、逗号和命名参数等 token，并在尽可能早的位置发现非法字符、未闭合字符串、数字格式错误等问题。",
        "中文金融需求进入系统后，最终仍要落到 DSL 或候选 DSL 上。用户可能混用大小写、数字、引号和空格，词法层需要保持足够宽容，同时不能把不合法内容悄悄吞掉。错误定位越早，诊断越容易对用户友好。",
        "项目没有把词法分析做成一个无意义的包装。后续 parser、semantic analyzer 和 SQL generator 都依赖 token 的准确边界，尤其是字符串字面量、命名参数和比较运算符。这里出错，后面的所有证据都会失去基础。",
    ],
    "语法分析": [
        "Parser 把 token 流转成 AST。AST 中保留函数调用、比较表达式、布尔组合、命名参数、数值字面量和字符串字面量等结构，后续模块不再处理原始文本片段。这样做能避免很多字符串拼接式编译器常见的问题。",
        "语法树还有展示价值。Web Demo 中的 AST 标签页能让评委看到系统确实理解了输入结构，而不是在样例库里匹配字符串。对于复杂表达式，AST 比 SQL 更适合解释“用户想表达什么”。",
        "Parser 的错误信息也要可控。括号缺失、参数缺失、逗号位置错误等问题会在语法阶段返回稳定诊断，避免用户看到 Python traceback。企业级工具的成熟感，很多时候就体现在这些失败路径上。",
    ],
    "语义分析": [
        "语法正确不代表业务语义正确。Semantic analyzer 会继续检查指标是否存在、函数参数数量是否匹配、窗口是否为正整数、rank 参数是否冲突、filter 条件是否返回布尔值、顶层表达是否是关系结构。",
        "这一步是系统安全边界的一部分。用户不能通过裸字段绕过 indicator，也不能把直接 SQL 片段塞进 DSL。未知指标会返回 UNKNOWN_INDICATOR，并给出接近拼写的修复建议；非法窗口会明确指出参数要求。这种反馈比数据库报错更接近真实产品体验。",
        "语义分析还支撑后续优化。只有知道某个 SUM 窗口来自支持 prefix 的指标，编译器才会尝试 prefix-sum rewrite；只有知道表达式依赖窗口，日期下推策略才会收紧。语义信息越准确，优化越不会越界。",
    ],
    "配置注册表": [
        "Registry 把指标、物理表、列名、市场枚举、前缀表和函数元数据集中管理。这样编译器核心不需要知道每个指标来自哪张表，只需要询问 registry。配置层一旦稳定，新增指标的成本会明显下降。",
        "以 money_flow 为例，main_net_inflow 不是 daily_quote 上的基础字段，它需要通过 ts_code 和 trade_date 从辅助表 join。registry 记录这个来源，SQL generator 才能自动选择正确 join 策略。市场过滤、大小写容错和 prefix 支持也以同样方式管理。",
        "这套设计对隐藏用例很有价值。评委如果追问“新增一个指标怎么做”，答案不应该是改一堆 if-else，而应是增加配置、补 reference 支持、补测试用例、生成报告。Registry 正是这个回答的工程基础。",
    ],
    "SQL 生成流程": [
        "SQL generator 接收已通过语义分析的 AST，然后按关系阶段构造 CTE。普通过滤、窗口特征、布尔滚动、排名和最终筛选会被放在合适的层级里，避免生成看似简短但数据库无法执行的 SQL。",
        "生成器会同时输出 trace 和 explain。trace 适合人读，说明选择了哪些 rewrite；explain 适合报告和 Demo 读取，记录规则名、状态、消息和证据字段。这样优化行为不是藏在代码里，而是能被现场展示出来。",
        "需要强调的是，SQL 生成不是字符串模板替换。生成器会根据表达式依赖决定是否引入辅助表、是否构造窗口层、是否使用 prefix 表、是否需要 rank 子查询。这个差异决定了项目技术含量，也决定了它能否处理隐藏组合条件。",
    ],
    "特征物化层": [
        "窗口特征物化层解决的是 SQL 执行顺序问题。`close > MA(close, 3)` 这类表达式不能直接在 WHERE 中调用窗口函数，系统会先生成包含 `AVG(close) OVER (...)` 的内层查询，再在外层用计算好的列进行比较。",
        "这种分层也让多个窗口特征可以共享同一股票日期骨架。复杂表达式里可能同时出现 MA、MAX、CONS 或 EXIST，统一的特征层比临时拼接多个嵌套查询更容易维护，也更容易在 AST 与 SQL 之间建立对应关系。",
        "在 Demo 中，特征列通常带有内部命名，例如 `__win_1`。这些名字不是给业务用户直接使用的，而是为了让 SQL 结构和 explain 更清楚。答辩时可以指出：内部列名代表编译器生成的中间语义，不是用户手写 SQL。",
    ],
    "多表 join 策略": [
        "daily_quote 是项目里的股票日期主骨架，money_flow 和 stock_universe 是辅助数据源。编译器围绕 daily_quote 保持全集，再按指标需要引入 LEFT JOIN，避免辅助表缺失数据时把原本存在的股票日期行误删。",
        "金融数据源常常覆盖不一致。行情表通常最完整，资金流、财务、公告、行业分类可能有滞后或缺口。如果 join 策略过于激进，筛选结果就会混入数据覆盖偏差，而不是用户真实表达的业务条件。",
        "Join 设计同时影响 prefix 表构建。对于稀疏辅助源，prefix 表要基于 daily_quote 的交易日骨架生成，再把辅助值左连接回来，否则滚动窗口的 row_no 会被稀疏数据打乱。项目在文档和脚本中明确了这一点。",
    ],
    "Doris SQL Validator": [
        "SQL validator 是生成 SQL 之后、执行之前的安全检查。它会确认输出是单条查询语句，拒绝 DDL、DML、危险 token 和未知表引用，并检查窗口函数没有泄漏到 WHERE 等不合适的位置。",
        "这道检查对 AI 辅助尤其重要。即使未来接入真实大模型，模型也只能提出 DSL 候选；最终 SQL 必须由本项目生成，并通过 validator。直接 SQL 响应会被识别为不安全输入，不会进入执行链路。",
        "通过验证的 SQL 会在 explain 中留下 DORIS_SQL_VALIDATION 记录。这个小细节对答辩有帮助，因为它证明安全边界不是口头声明，而是编译结果的一部分。",
    ],
    "Doris 兼容性": [
        "项目以 Apache Doris 的 MySQL 兼容查询端口为目标，而不是只面向 SQLite。SQLite 在本地测试中承担快速执行和回归验证职责，但性能结论必须来自 Doris 集群证据。两者分工清楚，文档中也不把 SQLite 结果包装成 Doris 性能。",
        "Doris schema 使用 trade_date 自动分区、ts_code hash distribution 和 colocate group。基础表、辅助表和 prefix 表围绕股票代码与交易日组织，便于日期裁剪、窗口计算和 prefix join 在计划中呈现清楚结构。",
        "生成 SQL 时会避免依赖 SQLite 独有语法。窗口函数、CTE、COUNT、EXPLAIN 和字符串转义都按 Doris 可执行路径设计。这样的兼容性工作不显眼，却是项目能从本地 demo 走到真实 Doris evidence 的前提。",
    ],
    "长窗口瓶颈": [
        "金融筛选经常使用 60 日、120 日、250 日这类长窗口。直接窗口函数在语义上直观，但在大规模股票日期数据上会反复扫描历史区间，尤其是滚动 SUM 这类可累加指标，很容易成为查询耗时的主因。",
        "赛题关注高性能 Doris SQL，长窗口正是最适合展示优化能力的地方。如果项目只给出短窗口样例，评委很难判断它是否真的解决了数据库性能问题。因此，120 日成交量累计被选为规模实验主路径。",
        "优化不能牺牲语义。窗口边界、股票分区、交易日排序、日期范围和辅助表稀疏性都必须保持一致。prefix-sum 的设计价值就在于，它改变计算方式，但不改变 DSL 语义。",
    ],
    "前缀和优化原理": [
        "prefix-sum 的核心公式很简单：某一行的 N 日窗口和，等于当前累计值减去 N 日窗口之前那一行的累计值。对同一只股票按交易日编号后，`window_sum(i,N)=prefix(i)-prefix(i-N)`。复杂度从每行聚合 N 个历史值，变成查两个累计点并做一次减法。",
        "在 SQL 层，这个思路通常表现为 prefix 表自连接或热点物化列。基础表先生成 row_no 和累计值，查询时根据当前 row_no 找到历史行，再计算差值。对于长窗口，减少的不是一两次函数调用，而是大量重复历史扫描。",
        "项目没有把 prefix-sum 作为无条件优化。只有 registry 标记支持 prefix 的指标、函数是滚动 SUM、窗口参数合法且数据模型满足股票日期骨架时，才会触发 rewrite。否则系统继续使用普通窗口 SQL，确保正确性优先。",
    ],
    "热点窗口物化列": [
        "在比赛场景中，120 日成交量累计是很典型的热点查询。项目为 volume 的 120 日窗口配置了 `volume_sum_120` 物化列，让 optimized SQL 可以直接读取 prefix 表中的预计算结果，而不必在查询时再做 prefix 自连接。",
        "这条路径在 Doris 5M 规模证据中发挥了主要作用。baseline 使用窗口函数，optimized 使用 prefix 表与热点列，两者 COUNT 结果一致，平均延迟从 5182.042 ms 降到 142.993 ms。计划中也能看到 prefix table 标记，说明加速来自物理设计和查询改写，而不是缓存偶然命中。",
        "热点物化列不是泛化能力的替代品。它适合高频窗口、固定指标和竞赛重点样例；更广泛的窗口仍可通过普通 prefix 计算或窗口函数覆盖。文档在这里保持区分，避免把单个优化说成所有查询都同等加速。",
    ],
    "日期裁剪与分区剪枝": [
        "Doris 按 trade_date 自动分区后，日期条件能显著影响扫描范围。普通筛选中，下推日期上下界是自然选择；但遇到窗口语义时，下界可能会截断历史行，导致窗口值偏小。这里需要编译器理解语义，而不能只做字符串层优化。",
        "项目对 date_between 做了分情况处理。非窗口条件尽量完整下推，窗口条件保留计算所需历史，prefix-sum 路径则利用 row_no 与历史 prefix 行关系，在保证语义的前提下减少扫描。这个策略会体现在 trace 和 SQL 结构里。",
        "分区剪枝的价值在答辩中应该和正确性一起讲。只说“下推更快”是不够的，因为错误下推会改变结果；FinDSL Forge 的亮点是先识别哪些下推安全，再让 Doris 的物理分区发挥作用。",
    ],
    "Doris 证据设计": [
        "Doris 证据不是临时手工测一次时间。`prepare_doris_scale_evidence.ps1` 会启动 Docker Doris，生成确定性 CSV，应用 schema，清理旧数据，Stream Load 三张基础表，重建 prefix 表，采集 EXPLAIN、COUNT 和多次延迟，再更新 readiness。",
        "实验使用 5,000,000 行 daily_quote 数据，并在计时阶段禁用 SQL cache。baseline 与 optimized 都要执行成功，行数都要等于 88586，baseline 计划要包含 window，optimized 计划要包含 prefix table，加速比要超过阈值。任何一个条件失败，都不应该宣称性能达标。",
        "这种证据设计方便复核。评委或队友不需要相信一段口述，只要环境具备 Docker Doris 和 MySQL client，就可以按脚本重新运行。即使现场无法拉起容器，submission_artifacts 中的 evidence snapshot 也能说明当前提交对应的历史结果。",
    ],
    "AI 辅助定位": [
        "AI 在本项目中的角色是输入助手，而不是数据库代理。中文自然语言可以帮助用户更快描述筛选意图，但最终进入核心链路的必须是 DSL。这样既利用了大模型在语言理解上的优势，又避免把 SQL 执行权交给不可控输出。",
        "这种定位符合金融场景的基本要求。策略筛选涉及数据权限、口径一致和结果解释，不能因为模型一句话就绕过语义分析。AI 参与“提出候选”，编译器负责“判断候选是否可执行”。",
        "答辩中可以把它讲成一种务实的大模型集成方式。项目没有回避 AI，也没有把 AI 神化；它把 AI 放在清楚的边界内，让确定性程序承担审计和验证责任。",
    ],
    "NL2DSL 模板层": [
        "NL2DSL 模板层覆盖了一批官方风格表达，包括连续主力净流入、低价 bottom 排名、换手率百分比、B 股均量阈值、日期区间均线、滚动最小值、日期前缀和和负值资金流条件。它优先解决比赛中最可能出现的中文需求。",
        "模板层也处理真实用户常见写法。斜杠日期、中文年月日、近半年、大小写市场代码、负数阈值等输入，都可以被标准化到 DSL 候选。候选会携带 rule、confidence 和 rationale，方便 Demo 展示翻译依据。",
        "模板不是终点。它只是产生候选的第一步，候选仍然要经过完整编译和验证。这样即使模板命中不完美，也不会直接污染 SQL 执行结果；系统会在后续环节给出诊断或拒绝。",
    ],
    "LLM 候选安全环": [
        "LLM adapter 用于离线验证模型输出。它可以从 JSON 或 markdown 风格响应中提取候选 DSL，同时识别直接 SQL、空候选和明显不合法内容。直接 SQL 会被标记为 UNSAFE_DIRECT_SQL，不会进入数据库路径。",
        "有效候选也不是立刻放行。系统会继续编译 DSL、运行 Doris SQL validation，并在可用数据集上执行 SQL/reference equivalence。模型提供的 rationale 可以展示给用户，但不能替代编译器判断。",
        "这个安全环为后续接入真实 provider 留出了接口。无论使用 OpenAI、国产模型还是本地模型，外部模型只改变候选来源，不改变项目的安全边界。对于评委来说，这说明系统具备扩展空间，同时没有为了演示效果牺牲底线。",
    ],
    "诊断与修复建议": [
        "好的诊断应该告诉用户错在哪里、为什么错、怎么改。系统对未知指标、非法窗口、rank 参数冲突、非法日期、裸字段绕过和直接 SQL 等情况都返回稳定 diagnostic code，并尽量附带修复建议。",
        "例如用户输入 `indicator(\"clos\")`，系统不会让 Doris 报列不存在，而是在语义阶段返回 UNKNOWN_INDICATOR，并建议 `indicator(\"close\")`。这种体验对比赛演示很有价值，因为负例不再只是失败，而是展示系统成熟度的机会。",
        "诊断也服务于测试。official negative cases 不只要求失败，还要求失败方式符合预期。这样可以防止后续改动把清楚的业务错误变成模糊异常，保持产品层面的可用性。",
    ],
    "逻辑数据模型": [
        "当前逻辑模型保持克制，主要包含 daily_quote、money_flow 和 stock_universe。daily_quote 提供 ts_code、trade_date、close、turnover_rate、volume 等核心行情字段；money_flow 提供 main_net_inflow；stock_universe 提供市场类型。",
        "这个模型足以覆盖赛题的关键语义：市场过滤、价格指标、成交量窗口、换手率排名、资金流连续性和日期区间。模型没有一次性引入大量复杂表，原因是比赛首先需要证明核心链路扎实，而不是靠字段数量制造规模感。",
        "后续扩展时，真实行情、财务、行业和公告数据可以沿用同一套骨架。关键是保持 ts_code 与 trade_date 的主键语义，明确辅助表的覆盖范围，并在 reference evaluator 中补齐对应口径。",
    ],
    "Doris 表设计": [
        "Doris 表设计围绕两类目标展开：让查询能跑得快，让执行计划能解释清楚。trade_date 自动分区用于日期裁剪，ts_code hash distribution 用于股票维度分布，colocate group 用于减少相关表 join 的数据移动。",
        "基础表和 prefix 表的关系也很明确。基础表保存原始行情与辅助指标，prefix 表保存按股票交易日排序后的 row_no、累计值和热点窗口列。optimized SQL 使用 prefix 表时，计划形态能直接反映优化路径。",
        "本地 quickstart 为 Windows Docker Desktop 做了低内存参数调整。它适合比赛开发和证据采集，但文档也说明生产环境应提高 replication_num、bucket 数和 BE 数量。这样既能跑通本机，又不把本机配置误描述成生产最佳实践。",
    ],
    "本地 Docker 环境": [
        "项目提供 `deploy/doris/docker-compose.quickstart.yaml`，用于在本机拉起单 FE/BE Doris 环境。Windows 用户需要先安装 WSL2、Ubuntu 和 Docker Desktop，再由脚本启动容器；MySQL client 只用于连接 Doris 的 9030 查询端口，不需要再安装 MySQL Server。",
        "网络环境不稳定时，脚本支持通过 `-ProxyUrl \"http://127.0.0.1:7897\"` 使用本地代理拉取镜像。这个参数对当前开发机很实用，因为 Docker 拉镜像和 GitHub push 都可能受网络影响。",
        "容器环境的目标是可复现，不是替代生产集群。答辩时可以说明：本机 Doris 用于证明 SQL 可执行和优化有效，多节点 Doris 是后续企业化增强方向。这样表述更稳妥，也更符合真实工程分阶段交付方式。",
    ],
    "Stream Load 流程": [
        "小样本 SQL 可以直接插入，但 5M 规模实验必须使用 Doris Stream Load。脚本会先生成 deterministic CSV，再调用 Doris HTTP 接口加载 daily_quote、money_flow 和 stock_universe，最后重建 prefix 表并采集证据。",
        "Stream Load 的好处是贴近 Doris 实际导入方式，也能在日志中看到每张表的加载状态。相比手工复制 SQL，它更适合重复实验，尤其是需要多次清理旧数据、重建表和控制批量导入顺序时。",
        "这条流程对比赛提交很关键。只有数据导入、schema、prefix 构建和 evidence 采集被脚本串起来，团队才能在环境恢复或机器变更后重新跑出同类证据。否则性能结果很容易变成一次性记录。",
    ],
    "真实数据接入": [
        "合成数据用于可复现实验，真实数据用于增强业务可信度，两者不应混在一起讲。5M 合成数据的优势是稳定、可重跑、便于控制规模；真实行情样例的优势是更贴近评委对金融业务的直觉。",
        "接入真实数据时，需要保持字段口径与当前 schema 一致。ts_code、trade_date、close、turnover_rate、volume、main_net_inflow 和 market 是当前核心字段；如果新增财务或行业数据，也要在 registry 和 reference evaluator 中同步定义。",
        "答辩材料中建议明确标注数据来源。性能证明使用合成大样本，业务演示使用真实或公开小样本，这样既不夸大真实数据规模，也不削弱性能实验的可复现性。",
    ],
    "安装与基础检查": [
        "普通开发只需要 Python、Git 和项目源码；Doris 规模证据需要额外准备 WSL2、Ubuntu、Docker Desktop、MySQL client 和可用网络代理。MySQL client 用来连 Doris，不承担数据库服务端角色，这一点容易混淆。",
        "基础检查建议按顺序执行：确认 `python -m pytest -q` 能跑，确认 `scripts/serve_demo.ps1` 能启动 Web Demo，确认 `mysql.exe` 已进入 PATH，最后再尝试 Doris quickstart。不要一开始就排查 Doris 容器，否则容易把 Python 或路径问题误判成数据库问题。",
        "如果 Docker 镜像拉取失败，优先检查代理端口和 Docker Desktop 的 WSL 集成；如果 Doris 启动但连接失败，检查 9030 端口和容器健康状态；如果 SQL 执行失败，再回到 schema、数据导入和 prefix 表构建。排查顺序清楚，能节省很多时间。",
    ],
    "CLI 编译操作": [
        "CLI 是最直接的编译入口。`python -m findsl.cli compile` 后接 DSL，可以输出 Doris SQL；加上 `--json` 后，还能看到 AST、trace、explain 和编译耗时。开发阶段建议多用 JSON 输出，因为它比肉眼看 SQL 更容易定位问题。",
        "答辩前至少准备三类 CLI 示例：普通指标过滤、窗口查询、prefix-sum 查询。普通示例证明基础编译，窗口示例证明 SQL 层级处理，prefix 示例证明优化器会选择不同执行路径。三条命令比一条复杂长命令更容易讲清楚。",
        "CLI 也适合快速复核隐藏需求。拿到新表达后，先用 diagnose 或 compile 看语义是否成立，再用 verify-sql 做 reference 对照，最后才考虑是否需要 Doris evidence。这个流程比直接改 Demo 代码稳得多。",
    ],
    "诊断操作": [
        "`diagnose` 命令用于检查非法 DSL。它返回 diagnostic code、消息和修复建议，适合展示系统如何处理负例。比赛中负例演示很重要，因为它能说明项目不是只为正例样例写死。",
        "建议准备 UNKNOWN_INDICATOR、INVALID_WINDOW、UNSAFE_DIRECT_SQL 和 rank 参数冲突等案例。每个案例都要能解释清楚：系统在哪一层发现问题，为什么不能放行，用户应该怎样修改。",
        "诊断输出还能帮助开发者扩展 DSL。新增函数或指标后，如果错误码变得模糊，说明语义检查没有跟上；如果建议不准确，说明 registry 或相似度提示需要调整。诊断质量本身就是工程成熟度的一部分。",
    ],
    "Web Demo 操作": [
        "Web Demo 是面向评委的主展示界面。`scripts/serve_demo.ps1` 默认启动 8765 端口，页面提供中文需求输入、DSL 输入、样例选择、SQL/AST/Explain/Rows/Evidence 标签页和 Copy SQL 按钮。现场演示时，它比 CLI 更容易让非开发背景听众跟上。",
        "推荐演示顺序是：先输入官方风格中文需求，展示候选 DSL；再打开 AST 和 SQL，说明确定性编译链路；随后切换 prefix-sum 正例，展示 explain 和 evidence；最后选择一个负例，展示诊断码和修复建议。这样五分钟内能覆盖友好输入、严谨编译、性能优化和失败处理。",
        "如果现场 Doris 容器不可用，不要临时冒险重配环境。可以展示已经版本化的 Doris evidence snapshot，并说明 Demo 当前使用本地样本做语义验证，规模性能由独立 Doris 证据支撑。这个说法诚实，也更像正式交付。",
    ],
    "Readiness 操作": [
        "`submission_readiness.ps1` 是提交前总门禁。它会检查测试、官方套件、语义等价、benchmark、defense package、Doris evidence marker、submission artifacts 和 Git 状态，最后生成 `reports/submission_readiness.md`。",
        "理想提交状态是 blocking gates passed 为 true，warning count 为 0。当前项目已经达到这个状态，说明核心测试、Doris 规模证据和提交快照都能被脚本识别。后续每次关键改动后都应重新运行 readiness，不要只凭单个测试通过就判断可以提交。",
        "readiness 报告也适合答辩使用。它把分散的命令结果集中在一份文件里，能够快速回答“你们现在到底完成到什么程度”。对国家级奖项目标来说，这种总验收文件比口头保证更有分量。",
    ],
    "单元测试体系": [
        "测试覆盖 parser、compiler、semantic、diagnostics、nl2dsl、llm_adapter、doris_sql、doris_evidence、demo 和 readiness。当前全量 pytest 为 169 passed，说明收益率算子、官方套件和文档增强没有破坏核心链路。",
        "测试设计关注高风险行为。比如窗口函数不能出现在 WHERE，未知指标要给修复建议，prefix rewrite 不能改变结果，LLM 直接 SQL 要被拒绝，Demo API 要返回稳定字段。它们不是为了凑数量，而是围绕赛题失分点布防。",
        "后续新增功能时，应先补参考语义和测试，再修改 SQL generator。尤其是新增窗口函数、指标表或优化规则，必须保证正例、负例和 equivalence 同步更新。否则功能越多，隐藏风险越大。",
    ],
    "官方风格覆盖套件": [
        "official_positive_cases.jsonl 和 official_negative_cases.jsonl 是比赛风格的核心回归语料。正例覆盖窗口、排名、日期、市场、资金流、prefix-sum 和热点窗口；负例覆盖未知指标、非法参数、危险 SQL、日期错误和语义绕过。",
        "正例不只检查能否编译成功，还会检查 SQL 片段、trace 片段、explain 规则和 SQL/reference 等价。这样可以防止系统生成一段语法正确但绕过优化、缺少安全验证或语义漂移的 SQL。",
        "负例要求返回预期 diagnostic code。这个要求比简单地“失败即可”更严格，因为真实产品需要可预期的错误行为。答辩时展示负例套件，能让评委看到项目对隐藏错误有准备。",
    ],
    "语义等价验证": [
        "语义等价验证采用两条独立路径。Pandas reference evaluator 直接解释 DSL，SQLite executor 执行编译生成的 SQL，两边结果按 ts_code 和 trade_date 比较。只要出现 missing 或 extra，就说明编译链路存在语义偏差。",
        "这套机制特别适合发现窗口和日期问题。SQL 看上去可能很合理，但下界裁剪、rank 分区或辅助表 join 只要错一点，结果集就会变化。reference evaluator 作为慢但清楚的基准，能让这些问题尽早暴露。",
        "需要注意，SQLite 等价验证不是 Doris 性能证明。它是本地正确性门禁，目的是让每次改编译器都能快速检查语义。性能和计划形态仍然由 Doris evidence 单独证明。",
    ],
    "Doris 规模验证": [
        "Doris 规模验证把项目从本地小样本推到真实数据库执行。collector 会在 Doris MySQL 兼容端口上执行 baseline 和 optimized SQL，采集 EXPLAIN、COUNT 和多轮延迟，并把结果写入 Markdown 与 JSON。",
        "当前关键结论是 5M 行数据、行数 88586/88586 一致、baseline 平均 5182.042 ms、optimized 平均 142.993 ms、加速 36.24x。这个结论已经被 readiness 读取，用于关闭 Doris-scale performance proof 的提交警告。",
        "答辩中不要只说“快了 36 倍”。更完整的说法是：同一 DSL 生成两条语义等价 SQL，baseline 使用窗口函数，optimized 使用 prefix 热点列，SQL cache 禁用，COUNT 行数一致，计划标记符合预期。这样结论才经得起追问。",
    ],
    "提交包证据": [
        "`reports` 目录适合本地生成和调试，但提交材料需要更稳定的快照。`scripts/export_submission_artifacts.ps1` 会把关键报告复制到 `submission_artifacts/evidence_snapshots`，形成可版本化证据包。",
        "证据快照包括 readiness、official suite、defense package、Doris evidence 等轻量文件。它们不包含 5M 原始数据，也不包含临时渲染图片，因此适合进入 Git。这样仓库既不会臃肿，又能保留评审需要的核心记录。",
        "提交前应检查快照时间和 Git commit 是否匹配。如果代码已经改动但 artifacts 没有重新导出，文档中引用的证据就可能和当前版本不一致。这个细节在正式比赛提交中很容易被忽略。",
    ],
    "答辩主线": [
        "答辩建议从痛点开始。金融选股表达复杂，手写 SQL 容易出错；大模型直接生成 SQL 风险高；长窗口在数据仓库中成本大；比赛要求的不只是演示，而是正确性、性能和复现。这个开场能把项目放到真实问题里，而不是从技术名词堆砌开始。",
        "方案部分再讲四层：FinDSL 表达业务意图，确定性编译器生成 Doris SQL，reference 与 validator 保证正确和安全，prefix-sum 与热点窗口证明性能。每层都对应 Demo 或报告，听众能看到问题如何被逐步拆解。",
        "结尾用证据收束。169 passed、32/32 正例、34/34 负例、5M Doris、36.24x、readiness warning 0、GitHub 与 bundle 回溯，这些数字不需要一次性全念完，但要在关键节点自然出现，让评委相信项目状态是真实可复核的。",
    ],
    "演示节奏": [
        "五分钟演示可以分成四段。第一分钟展示中文输入到 DSL 候选，说明 AI 只是辅助；第二分钟展示 AST、SQL 和 explain，说明编译器掌握语义；第三分钟展示 prefix-sum 案例和 Doris evidence，说明长窗口加速；最后一分钟展示负例诊断和 readiness。",
        "现场操作要避免过多切窗口。最好提前打开 Web Demo、evidence snapshot、readiness 报告和 PPT 对应页。讲到某个点时，只切到最能支撑它的界面，不要在文件夹里寻找报告。",
        "如果时间被压缩，优先保留“中文输入、prefix 证据、负例诊断”三步。它们分别代表易用性、技术门槛和工程可靠性，比单纯展示一大段 SQL 更能打动评委。",
    ],
    "PPT 组织": [
        "PPT 应该是讲解提纲，不是手册压缩版。推荐结构为：题目理解、痛点、总体方案、架构图、DSL 能力、正确性验证、Doris 性能、AI 安全、工程交付、创新点和后续规划。每页只承载一个结论。",
        "图和数字要服务叙事。架构页展示端到端链路，性能页只突出 baseline 与 optimized 对比，质量页放测试和 readiness 结果，AI 页强调候选 DSL 安全环。不要把所有命令、表格和源码截图都塞进 PPT。",
        "手册与 PPT 的关系应当明确：PPT 负责现场表达，手册负责赛后查阅。答辩时可以在页脚或备注里标注证据文件名，让评委知道完整材料并不只存在于口头讲述中。",
    ],
    "得分点映射": [
        "`score_mapping.md` 已经把赛题要求映射到模块、脚本和证据。DSL 解析对应 lexer、parser 和 AST；语义校验对应 semantic 与 diagnostics；Doris SQL 对应 sqlgen 和 validator；性能对应 prefix-sum、hot-window 和 Doris evidence；AI 对应 nl2dsl 和 llm_adapter。",
        "得分点映射的意义在于减少答辩时的随机性。评委问到某项要求时，团队可以直接回答“实现在哪、证据在哪、如何复现”，而不是临场回忆。对于多模块项目，这种映射会让讲解更像成熟交付。",
        "提交前应把映射表和最新 readiness 对齐。如果某个得分点已经增强，映射也要更新；如果某项仍是未来规划，不能写成已完成。诚实区分状态，比把所有方向都说成完成更可靠。",
    ],
    "Git 工作流": [
        "项目当前使用 main 分支持续推进，关键节点完成后运行测试、提交、push，并生成 bundle 备份。GitHub 远端和本地 bundle 形成两条回溯路径，能降低网络、误操作或本机环境变化带来的风险。",
        "开发阶段要保持提交粒度清楚。功能、文档、证据、样式和环境脚本尽量不要混在一个巨大提交里；但临近比赛提交时，也不要长期保留未提交的本地改动。可回溯性比“暂时先放着”更重要。",
        "每次 push 前建议确认 `git status --short`、最近 commit、readiness 和 artifacts。这样即使团队成员切换机器，也能快速知道远端版本是否就是当前可演示版本。",
    ],
    "Bundle 备份": [
        "Git bundle 是离线仓库备份，适合在网络不稳定或远端不可访问时使用。它包含完整 Git 历史，不是简单的源码压缩包，因此可以恢复分支、提交和标签。",
        "当前 bundle 目录位于 `研究生金融科技创新大赛/git_bundles`。重要提交后生成新 bundle，可以把代码、文档和证据快照一起固定下来。比赛前建议保留至少最近两到三个关键版本，避免误删后只剩一个损坏备份。",
        "bundle 不能替代正常 GitHub push。远端仓库适合协作和云端回溯，bundle 适合本地离线保险。两者并行，才符合高风险提交前的稳妥做法。",
    ],
    "风险清单": [
        "当前剩余风险主要包括真实行情样例还可以进一步丰富、最终答辩视频需要录制、真实 LLM provider 尚未接入、多 BE Doris 生产形态尚未实测。Web Demo 截图已经进入 `submission_artifacts/demo_screenshots/`，不会再依赖临场手动截屏。这些风险不会推翻核心赛题完成度，但会影响展示丰满度和企业化延展性。",
        "文档中应把这些内容写成“可选增强”或“后续规划”，不要包装成已经完成的交付。比如本地单 FE/BE Doris 已足以支撑比赛证据，但多节点 Doris 仍是下一阶段；离线 LLM adapter 已验证安全环，真实 provider 接入仍需单独测试。",
        "风险管理不是示弱。相反，能清楚说明哪些已经验证、哪些还在规划，往往会让评委更信任项目。过度承诺最容易在追问中暴露问题。",
    ],
    "质量门禁": [
        "项目质量门禁分三层。日常开发至少跑相关 pytest；涉及 DSL、SQL 或诊断的改动要跑 official-suite 和 equivalence；涉及 Doris schema、prefix 或性能路径的改动必须重新采集 Doris evidence 并运行 submission readiness。",
        "门禁的重点是让失败尽早出现。parser 改动不应该等到 Demo 报错才发现，SQL generator 改动不应该等到 Doris 执行才发现语义偏差，性能优化也不应该只看本地 SQLite 时间。每一类风险都有对应检查点。",
        "提交阶段建议把 readiness 当作最终准入条件。只有 blocking gates passed、warning count 为 0、Git 状态可解释、artifacts 已导出，才进入最终打包和答辩材料更新。这个习惯能减少临近截止时的混乱。",
    ],
    "真实数据样本": [
        "真实数据样本是提升业务可信度的下一步。规模不必一开始很大，几只股票、数百个交易日、覆盖 close、volume、turnover_rate、main_net_inflow 和 market，就足以展示字段口径和真实金融表达。",
        "真实样本最好用于 Demo 体验，而不是替代 5M 性能基准。评委看到真实行情会更容易理解选股语义；而性能结论仍应基于可重跑的大规模合成数据。两类数据各司其职，材料表达会更稳。",
        "接入时需要同时更新数据说明、样例查询、reference 验证和可能的截图。不要只把 CSV 放进目录里就算完成，真实数据的价值来自可解释来源、字段口径和演示链路。",
    ],
    "多节点 Doris": [
        "当前本地 quickstart 是单 FE/BE，已经能证明 SQL 可执行和 prefix 优化有效。若继续冲刺企业级交付，多 BE Doris 集群是很自然的增强方向，因为它能验证分布式执行、replication_num、bucket 数和 colocate group 在更真实环境中的效果。",
        "多节点测试重点不只是跑通容器数量。需要观察 Stream Load 并发、数据分布、查询计划、节点资源和失败恢复。baseline 与 optimized 的对比也要重新采集，不能沿用单节点证据。",
        "这项增强适合放在后续规划或冲刺加分项。它有门槛，也能体现工程深度，但需要更多机器资源和调参时间。若时间有限，应优先保证当前单节点证据、文档和答辩材料足够稳。",
    ],
    "物化视图与增量维护": [
        "prefix 表当前由脚本重建，适合比赛复现和确定性实验。生产系统中，长期全量重建并不一定合适，尤其当行情数据每日更新、窗口指标增多时，增量维护就会变得重要。",
        "后续可以研究 Doris materialized view、定时调度任务或增量 ETL，把热点窗口列从一次性实验资产变成持续更新的数据服务。需要关注的是刷新延迟、历史修正、分区重算和失败重试。",
        "这条路线能把项目从竞赛原型推向投研平台雏形。答辩时可以简要提及，但不宜占用过多时间；当前最强证据仍然是已经完成的 prefix-sum rewrite 和 5M Doris 实测。",
    ],
    "真实 LLM Provider": [
        "离线 LLM adapter 已经验证了候选提取和安全拒绝逻辑，真实 provider 接入可以作为增强项推进。接入后，用户体验会更接近完整 AI 产品：自然语言输入由模型生成多个 DSL 候选，系统再逐一验证。",
        "安全边界必须保持不变。模型不能直接执行 SQL，不能绕过 semantic analyzer，不能跳过 SQL/reference equivalence。provider 的作用是扩大候选覆盖面，而不是替代编译器。",
        "评估真实模型时，应记录命中率、无效候选比例、危险输出比例和平均验证耗时。只展示一个成功例子意义有限，能量化模型在安全环中的表现，才更符合企业交付标准。",
    ],
    "更多 DSL 算子": [
        "DSL 已经新增 RET 区间收益率，后续还可以继续扩展波动率、成交额、行业中性、财务因子、公告事件和情绪指标。每个新增方向都要先判断是否属于筛选语义，是否能被 reference evaluator 解释，是否能编译成 Doris 友好的 SQL。",
        "扩展时应坚持配置优先。普通指标走 registry，复杂函数补语义检查和参考实现，性能敏感函数再考虑专门 rewrite。不要为了多展示几个算子，把核心编译器写成难以维护的样例分支集合。",
        "从比赛角度看，新增算子不是越多越好。更有竞争力的做法是选择两到三个有金融含义、有性能挑战、能形成证据的方向深入实现。项目当前的长窗口 SUM 就是这种思路的代表。",
    ],
}


SECTION_SUPPLEMENTS = {
    "优秀竞赛文档的共性框架": "落到本项目，文档框架还要承担“快速定位证据”的功能。比如评委问性能，材料应能立即指向 Doris evidence；问安全，能指向 validator 和 LLM adapter；问复现，能指向 readiness、bundle 和运行脚本。好的目录不只是排版顺序，它本身就是答辩路线图。",
    "本文档的定位": "这份文档后续可以直接作为团队交接材料使用。新成员不必先读完全部源码，也能知道哪些模块是核心、哪些脚本是入口、哪些报告能证明结论。对于竞赛项目来说，这种可交接性往往比临时整理出来的“展示稿”更能体现工程成熟度。",
    "读者对象与使用方式": "实际使用时可以按时间预算选择阅读深度。只有十分钟，就看摘要、赛题得分点和 Doris 证据；有半小时，就补读架构、DSL 和测试章节；准备答辩时，再把操作指南和演示节奏逐项跑一遍。文档的价值在于让不同角色都能带着问题进入，而不是被迫从第一页读到最后一页。",
    "赛题 19 的本质问题": "隐藏测试很可能不会和样例完全一致。它可能更换指标、组合多个窗口、改变排名方向或加入日期约束。项目的核心判断是：只有把这些变化抽象到语言和语义层，才能真正应对隐藏用例；如果依赖样例级 SQL 模板，项目在评审追问时会很快暴露边界。",
    "核心评价指标": "这些指标还可以转化为答辩页上的一句话：输入覆盖由 official suite 证明，语义正确由 reference equivalence 证明，规模性能由 Doris evidence 证明，提交状态由 readiness 证明。评委听到这条线，能迅速理解项目不是靠单点截图支撑。",
    "主要技术风险": "风险控制里有一个容易忽略的点：错误路径也要设计。比赛作品如果只展示成功样例，评委会担心系统对真实用户输入缺少韧性。项目把负例诊断、LLM 直接 SQL 拒绝、非法窗口和未知指标都纳入测试，正是为了让失败行为同样可预期。",
    "国家级奖项导向策略": "顶级奖项通常看重“完成度和亮点同时成立”。当前完成度已经比较扎实，下一步展示时要把亮点聚焦在有门槛的地方：Doris 长窗口优化、AI 安全环、语义等价验证和可回溯提交链。不要把篇幅浪费在普通项目都具备的启动命令上。",
    "产品定位": "从产品化角度看，FinDSL Forge 更像一个编译型中间层，而不是一个纯前端工具。它连接业务语言和数据仓库，把人类可读的金融表达转为数据库可执行计划，并保留每一步解释。这个定位能帮助评委理解项目为什么需要编译器、验证器和 evidence collector。",
    "核心用户画像": "不同用户对“好用”的定义并不相同。策略研究者希望少写 SQL，数据工程师希望 SQL 可控，评委希望证据清楚，导师希望方案有扩展空间。文档和 Demo 需要同时覆盖这些视角，所以界面展示、脚本复现和技术说明缺一不可。",
    "典型业务场景": "这些场景在真实投研中经常组合出现，例如先限定 A 股和日期区间，再判断 120 日成交量，再取每日换手率排名。组合之后 SQL 复杂度会明显上升，也正是编译器价值最容易被看见的时候。演示时应优先选择组合场景，而不是只跑单条件过滤。",
    "与普通文本转 SQL 的区别": "这个差异也决定了项目宣传口径。不能把 FinDSL Forge 简化成“AI 自动写 SQL”，那样会削弱项目真正的技术亮点。更准确的表述是：AI 帮助用户进入 DSL，编译器负责确定性转换，验证链路负责把输出变成可以被审计的数据库查询。",
    "分层架构概览": "架构图建议在 PPT 和手册中保持一致。输入、编译、验证、执行、展示五层不要频繁改名，否则答辩时容易出现概念漂移。稳定的架构语言能让团队在讲 NL2DSL、prefix-sum、readiness 时始终围绕同一张图展开。",
    "模块协作方式": "模块协作的另一个好处是便于替换实现。未来如果 SQLite 本地执行器换成 DuckDB，或者 LLM provider 从离线样例换成真实 API，只要输入输出契约不变，核心编译器和测试证据就不需要大改。这种可替换性是企业级架构的重要特征。",
    "证据链架构": "证据链应尽量自动生成，减少手工编辑。手工复制结果最容易出现报告和代码不一致：一次测试重跑后数字变了，文档却没更新。项目通过脚本导出 artifacts，就是为了把证据从“人工整理材料”变成“工程产物”。",
    "架构可扩展性": "扩展时要优先判断新增内容属于哪一层。如果只是新增指标，多半在 registry 和数据模型层解决；如果新增函数，需要语义和 reference 同步；如果新增优化，需要 explain、测试和 Doris evidence 一起补。分层思维能防止所有需求都涌入 SQL generator。",
    "语言设计原则": "受限 DSL 的一个重要优势是能给出更好的错误信息。通用 SQL 错误通常面向数据库开发者，而 FinDSL 的错误可以面向策略用户，例如“窗口必须为正整数”“指标 close 是否拼写错误”。这种差异直接影响产品体验。",
    "关系算子": "关系算子的组合能力也影响 explain 的表达。每个 filter、then、rank 都可以对应到 SQL 中的一段 CTE 或子查询，系统能把编译结果拆成评委听得懂的阶段。相比直接展示一条长 SQL，阶段化说明更适合现场讲解。",
    "窗口与聚合算子": "窗口算子后续扩展要谨慎。RET 收益率已经补齐，波动率、标准差等函数仍可继续加入，但每个函数都要明确窗口边界、空值处理、交易日缺失和 reference 语义。没有这些定义，函数列表再长也只是表面丰富。",
    "排名语义": "rank 的稳定性还关系到测试可重复性。没有 tie-breaker 时，某些数据库在指标相等时可能返回不同顺序，导致今天通过、明天失败。把稳定排序写进编译规则，可以避免这种难以排查的偶发问题。",
    "日期语义": "日期逻辑建议在答辩中配一个小例子说明：若筛选 3 月份但计算 120 日窗口，系统仍然需要读取 3 月之前的历史行。这个例子很直观，能帮助非数据库背景的评委理解为什么简单下推会错，也能突出项目处理细节的认真程度。",
    "词法分析": "词法层虽然不显眼，却是安全边界的一部分。字符串字面量、引号和符号如果处理不严，后面再强的 SQL validator 也会被迫处理更复杂的异常输入。把问题尽早切开，能让错误报告更清楚，也能降低后续模块负担。",
    "语法分析": "AST 还可以作为未来可视化和调试工具的基础。比如把 filter、rank、window、indicator 渲染成图形节点，评委或业务用户就能直接看到表达式结构。当前 Demo 已展示 JSON 形式，后续 UI 增强可以沿着这个方向继续。",
    "语义分析": "语义层不应该为了通过某个样例而放宽规则。比如允许裸字段看似方便，却会破坏指标注册和权限控制；允许 rank 参数混用看似灵活，却会制造含义不清的查询。严格规则是金融 DSL 的价值，而不是限制。",
    "配置注册表": "配置注册表也方便写文档和答辩。团队可以展示一个新增指标流程：配置指标元数据，补样本列，更新 reference，增加 official case，运行 readiness。这个流程比“进代码里找位置改”更符合企业平台的维护方式。",
    "SQL 生成流程": "SQL 生成的输出最好始终伴随 trace。只给 SQL，评委看到的是结果；给出 trace，评委能看到系统为什么这么生成。尤其是 prefix-sum、日期下推和 validator 通过记录，都是体现编译器智能程度的证据。",
    "特征物化层": "特征层的设计还方便定位性能问题。如果某个查询变慢，可以先看窗口特征数量、CTE 层级和是否触发 prefix rewrite，而不是直接盯着最终 WHERE。结构化 SQL 比一团嵌套表达式更利于调优。",
    "多表 join 策略": "后续接入财务或行业表时，join 策略要继续保持谨慎。财务数据常按报告期而不是交易日更新，行业分类可能按生效日期变化，这些都不能简单等同于 daily_quote 的 trade_date。当前 join 设计为这些扩展留下了讨论空间。",
    "Doris SQL Validator": "validator 不追求替代数据库优化器，它只负责守住项目自己的边界。SQL 是否最优由 Doris 和优化规则决定，但是否单语句、是否安全、是否引用已知表、是否符合窗口位置规则，必须由系统在执行前确认。",
    "Doris 兼容性": "兼容性还体现在证据采集方式上。项目通过 MySQL client 连接 Doris 9030 端口，采集真实 EXPLAIN 和 COUNT，而不是解析静态 SQL 文件。这样才能说明生成语句确实能在 Doris 上执行，而不是只符合语法想象。",
    "长窗口瓶颈": "这个瓶颈也可以从业务侧解释：长周期成交量、均线和高低点是选股里常见条件，用户不会因为数据库慢就放弃这些表达。系统如果能把这类条件优化好，就更接近真实投研工具，而不是只覆盖短小示例。",
    "前缀和优化原理": "prefix-sum 适合 SUM 这类可加指标，不适合所有窗口函数。MAX、MIN、MA、波动率等函数有不同的数学结构，需要不同优化策略。文档明确这一点，可以避免评委误以为项目把所有窗口都简单套同一个公式。",
    "热点窗口物化列": "热点列设计体现了工程取舍：比赛里高频、长窗口、易解释的查询值得预计算，低频或窗口参数变化大的查询则不一定值得。企业系统也常用类似思路，把资源投入到业务最常访问的路径上。",
    "日期裁剪与分区剪枝": "Doris 分区剪枝能带来收益，但它依赖 SQL 条件落在正确位置。编译器如果把日期条件放错层，可能既不能剪枝，又可能改变窗口结果。因此日期裁剪需要和 SQL 层级设计一起看，不能作为单独小优化处理。",
    "Doris 证据设计": "证据报告中行数一致非常关键。性能更快但结果不同没有意义，尤其在金融筛选中，少一只股票或多一只股票都可能改变业务判断。项目把 row count equivalence 放进 Doris evidence，是为了防止优化结果只追求速度。",
    "AI 辅助定位": "现场讲 AI 时建议避开泛泛而谈的大模型热词。更好的讲法是：用户语言不稳定，DSL 稳定；模型负责把不稳定输入转成候选，编译器负责把候选变成可信执行计划。这个角度更自然，也更能体现项目设计能力。",
    "NL2DSL 模板层": "模板层的竞争力不在于写了多少规则，而在于规则覆盖了赛题高频问题，并且输出能被后续链路验证。规则命中失败时，系统仍能让用户切回 DSL 或诊断路径，这比单一自然语言入口更可靠。",
    "LLM 候选安全环": "真实 provider 接入后，还需要考虑速率限制、超时、响应格式漂移和敏感信息处理。当前离线 adapter 先把候选解析和安全拒绝打牢，是合理的分阶段做法；它让后续接 API 时不必重新设计核心安全逻辑。",
    "诊断与修复建议": "诊断文案应保持稳定和克制。不要把错误解释写成大段泛泛建议，而要给出最可能的修复动作。比如未知指标就建议相近指标，非法窗口就指出正整数要求，直接 SQL 就说明系统只接受 DSL 候选。",
    "逻辑数据模型": "最小模型的好处是评委容易理解。三张表就能讲清楚行情、资金流和股票市场属性，再通过 join 和窗口组合出复杂筛选。等核心链路被认可后，再谈更多数据源，叙事会更有层次。",
    "Doris 表设计": "表设计章节建议配合 `deploy/doris` 下的 SQL 文件一起阅读。schema、sample data、prefix build 和 smoke queries 分开存放，既方便新手按顺序执行，也方便评委看到项目不是把数据库资产藏在代码里。",
    "本地 Docker 环境": "Windows 环境下最常见的问题是 WSL、Docker Desktop、PATH 和代理相互影响。文档把 MySQL client、Docker Doris 和代理参数分开说明，是为了让用户知道每个组件的作用，避免把所有连接问题都归因到 Doris。",
    "Stream Load 流程": "Stream Load 过程中如果失败，应先看 HTTP 返回体和 Doris FE 日志，再检查 CSV 列顺序、分隔符、表结构和权限。把这些排查点写入文档，可以让复现实验更像正式 runbook，而不是只给出一条命令。",
    "真实数据接入": "如果最终时间允许，建议准备一份小而干净的真实样例。它不需要承担性能证明，只要能让演示中的股票代码、交易日期和价格变化看起来真实，就能提升作品可信度。数据来源和脱敏说明要同步写清楚。",
    "安装与基础检查": "安装检查最好形成截图或日志证据。比如 `mysql --version`、Docker 容器状态、pytest 结果和 Demo 首页都可以作为答辩前自查项。这样出现现场问题时，团队能迅速判断是环境变化还是项目本身回归。",
    "CLI 编译操作": "CLI 输出还可以用于生成报告素材。把 `--json` 结果中的 AST、trace 和 explain 截取到文档或 PPT，比单纯复制 SQL 更能展示编译器内部能力。注意不要展示过长 JSON，选关键字段即可。",
    "诊断操作": "负例演示应控制节奏。先让用户看到错误输入，再展示诊断码和建议，最后修正后重新编译成功。这个小闭环能证明系统不仅会拒绝错误，还能帮助用户回到正确路径。",
    "Web Demo 操作": "Web Demo 的价值在于把多个证据面板放在同一页面。评委不用理解命令行，也能看到 DSL、SQL、AST、explain 和验证结果。后续 UI 增强可以继续围绕这个原则做，而不是增加无关装饰。",
    "Readiness 操作": "readiness 失败时不要简单重跑。应先看是哪一类 gate 失败：测试、official suite、Doris evidence、artifacts 还是 Git 状态。不同失败对应不同处理方式，盲目重跑只会掩盖根因。",
    "单元测试体系": "测试文件也能作为答辩材料的一部分。评委如果追问隐藏用例，团队可以指出测试覆盖了哪些边界条件，并解释新增用例如何进入 official suite。用测试回答问题，比临场承诺更有力量。",
    "官方风格覆盖套件": "官方风格套件应继续随赛题理解更新。每发现一种可能的评审输入，就把它变成正例或负例，而不是只在脑中记住。这样项目会越用越稳，隐藏用例准备也会从经验变成资产。",
    "语义等价验证": "等价验证结果建议在 Demo 和报告中都保留。它能向评委说明：编译生成 SQL 后，系统还用另一条语义路径核对结果。这个动作比“我们人工看过 SQL”更可信，也更符合金融系统的审慎风格。",
    "Doris 规模验证": "规模验证要避免过度包装。36.24x 是当前 5M 数据和特定 120 日成交量路径上的结果，不应泛化成所有查询都提升 36 倍。准确表述反而更专业，也能避免评委追问其他算子时陷入被动。",
    "提交包证据": "submission_artifacts 是评审最可能实际打开的目录之一。里面的文件命名、时间、内容和 README 提示都要保持清楚。项目越大，越需要让评委在有限时间内找到最关键的证据。",
    "答辩主线": "答辩时要减少空泛形容词，多用动作和证据。比如“系统会拒绝直接 SQL”比“系统很安全”更具体；“baseline 与 optimized 行数一致”比“优化有效”更可验证。语言越具体，越不像临时包装。",
    "演示节奏": "彩排时建议模拟网络不可用、Doris 未启动、端口占用和浏览器刷新等情况。只要提前准备好离线证据和备用命令，现场就不会因为环境波动打乱节奏。演示稳定性本身也是交付能力的一部分。",
    "PPT 组织": "PPT 中的每个数字都应能追溯到文件。36.24x 来自 Doris evidence，169 passed 来自 pytest，32/32 和 34/34 来自 official suite，warning 0 来自 readiness。数字旁边标注来源，会让材料更像正式工程汇报。",
    "得分点映射": "得分点映射还可以作为最终自检表。提交前逐项确认：是否有实现、是否有测试、是否有报告、是否能演示、是否能解释风险。任何一项缺失，都应在最后冲刺阶段补齐或诚实标注。",
    "Git 工作流": "Git 记录应当和竞赛节点对应起来。完成 Doris 证据、完成中文手册、完成 Web Demo 增强、完成最终提交包，都值得形成清楚提交。后续回看历史时，团队能知道每个里程碑对应哪个 commit。",
    "Bundle 备份": "bundle 备份最好在推送成功后立即生成，并把文件名带上时间戳。这样即使远端仓库短时访问异常，本地仍有完整恢复点。比赛提交前，这类低成本保险非常值得做。",
    "风险清单": "风险清单应定期更新，而不是写完就放着。每完成一项增强，就把它从风险或规划中移出；发现新问题，也要及时补进去。透明的风险管理能帮助团队把精力放在最影响得分的地方。",
    "质量门禁": "门禁结果最好和 commit 绑定。一个通过 readiness 的 commit 才是真正可交付版本；如果通过后又修改了代码或文档，就需要重新判断是否影响证据。这个纪律能避免“最后一分钟小改动”破坏稳定性。",
    "真实数据样本": "真实样本还可以服务产品故事。用真实交易日和股票代码展示 DSL，会让系统更像投研工具；用合成大样本展示性能，会让实验更可控。两者结合，比单独依赖一种数据更适合比赛展示。",
    "多节点 Doris": "多节点 Doris 如果实施，建议先写最小验收目标：容器或主机数量、数据规模、导入方式、查询集合、预期证据文件。没有验收目标就直接搭集群，很容易消耗大量时间却没有形成可展示结果。",
    "物化视图与增量维护": "增量维护还涉及数据修正问题。真实行情和财务数据可能回补或更正，窗口指标需要支持局部重算。把这类问题纳入规划，能让项目显得更懂生产数据链路，而不是只懂一次性跑实验。",
    "真实 LLM Provider": "真实模型评估时要保留失败样例。模型没有命中、输出格式不稳或给出危险 SQL，都是安全环价值的证据。只挑成功案例展示，反而会让评委怀疑系统是否真正处理了模型不确定性。",
    "更多 DSL 算子": "算子扩展应优先选择能形成明显差异化的方向。RET 已经把收益率纳入已完成能力；后续行业中性和财务因子能增强金融专业性，波动率能增强量化语义，公告情绪能体现多源数据能力。每个方向都要配套证据，而不是只写在规划里。",
}


def section_paragraphs(title: str, tag: str, idea: str, implementation: str, operation: str) -> List[str]:
    try:
        paragraphs = SECTION_PARAGRAPHS[title]
    except KeyError as exc:
        raise KeyError(f"Missing hand-written manual prose for section: {title}") from exc
    try:
        supplement = SECTION_SUPPLEMENTS[title]
    except KeyError as exc:
        raise KeyError(f"Missing hand-written manual supplement for section: {title}") from exc
    return [*paragraphs, supplement]


def write_markdown() -> str:
    lines: List[str] = [f"# {TITLE}", "", SUBTITLE, ""]
    lines.extend(["## 摘要", ""])
    lines.extend(summary_paragraphs())
    lines.extend(["", "## 参考框架学习结论", ""])
    for name, url, note in REFERENCE_LINKS:
        lines.append(f"- {name}：{url}。{note}")
    for idx, (chapter, sections) in enumerate(CHAPTERS, 1):
        lines.extend(["", f"## 第{idx}章 {chapter}", ""])
        lines.append(CHAPTER_INTROS[chapter])
        lines.extend(CHAPTER_DEEP_DIVES[chapter])
        for sec_idx, (section_title, tag, idea, implementation, operation) in enumerate(sections, 1):
            lines.extend(["", f"### {idx}.{sec_idx} {section_title}", ""])
            lines.extend(section_paragraphs(section_title, tag, idea, implementation, operation))
    lines.extend(["", "## 附录", ""])
    for title, paragraphs in APPENDIX_SECTIONS:
        lines.extend(["", f"### {title}", ""])
        lines.extend(paragraphs)
    return "\n\n".join(lines)


def summary_paragraphs() -> List[str]:
    return [
        "FinDSL Forge 面向中国研究生金融科技创新大赛赛题 19，解决的是金融选股表达如何稳定落到 Apache Doris 高性能查询上的问题。用户可以输入受限 DSL，也可以先用中文需求生成候选 DSL；系统随后完成 AST 构建、语义校验、Doris SQL 生成、SQL 安全检查和参考语义验证。整条链路强调可解释的工程行为，而不是把数据库执行权交给黑盒文本生成。",
        "当前项目已经形成可以支撑正式提交的证据基础。代码覆盖 lexer、parser、semantic analyzer、SQL generator、Doris SQL validator、Pandas reference evaluator、SQLite executor、Doris evidence collector、Web Demo 和 submission readiness；报告侧已有 169 项 pytest 回归、32/32 官方风格正例、34/34 官方风格负例、5,000,000 行 Doris 规模实验、36.24x 长窗口加速、warning count 为 0 的 readiness 结果，以及进入 `submission_artifacts` 的证据快照和 Web Demo 截图。",
        "这份手册把产品说明、赛题解读、架构设计、算法细节、部署步骤、操作指南、测试验证、答辩材料和后续规划放在一起。正文尽量采用企业技术文档的写法：先讲判断，再讲实现，再给出可复核的文件或命令；表格只承担对照和速查职责，不用来掩盖正文逻辑。",
    ]


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def build_docx() -> Tuple[Path, int]:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    configure_styles(doc)

    # Cover page
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(120)
    run = p.add_run(TITLE)
    set_run_font(run, "Microsoft YaHei", 24, bold=True, color="0B2545")
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_after = Pt(18)
    run = p2.add_run(SUBTITLE)
    set_run_font(run, "Microsoft YaHei", 13, color="1F4D78")
    add_callout(
        doc,
        "文档定位",
        "本文件是完整中文操作指南、技术白皮书、产品说明书、架构说明、算法说明、部署手册和答辩资料索引的合并版本，面向国家级奖项交付。",
    )
    meta = [
        ("项目名称", "FinDSL Forge"),
        ("竞赛方向", "研究生金融科技创新大赛赛题 19"),
        ("文档版本", VERSION),
        ("生成时间", GENERATED_AT),
        ("核心证据", "169 passed；官方风格 32/32 + 34/34；Doris 5M 规模 36.24x；readiness warning 0"),
    ]
    add_table(doc, ["项目", "内容"], meta, [2200, 7160])
    doc.add_page_break()

    # Header/footer on following pages
    section = doc.sections[0]
    header = section.header.paragraphs[0]
    header.text = "FinDSL Forge 中文综合操作指南"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in header.runs:
        set_run_font(run, "Microsoft YaHei", 9, color="555555")
    footer = section.footer.paragraphs[0]
    add_page_number(footer)

    add_heading(doc, "摘要", 1)
    for paragraph in summary_paragraphs():
        add_para(doc, paragraph)

    add_heading(doc, "目录与阅读路线", 1)
    toc_rows = []
    for idx, (chapter, sections) in enumerate(CHAPTERS, 1):
        toc_rows.append((f"第{idx}章", chapter, "；".join(section[0] for section in sections[:3]) + "。"))
    toc_rows.append(("附录", "命令、术语与提交建议", "用于提交前复核与现场答辩。"))
    add_table(doc, ["章节", "主题", "重点内容"], toc_rows, [1200, 2600, 5560])

    add_heading(doc, "参考优秀文档后的框架选择", 1)
    add_para(doc, "在撰写本手册前，先参考了竞赛项目开发文档模板、Diataxis 文档框架、Google 开发者文档风格指南、中文技术写作风格指南，以及 openEuler、OpenHarmony、Apache Doris 等大型工程项目的中文或官方文档。综合这些资料可以看到，优秀参赛项目文档通常不是单一说明书，而是同时包含背景论证、需求映射、技术设计、操作流程、测试证据、风险控制和附录索引。")
    add_para(doc, "因此本文采用“白皮书 + 操作手册 + 证据索引”的组合结构。白皮书部分负责说明为什么这样设计，操作手册部分负责说明如何使用和复现，证据索引部分负责说明哪些报告、脚本和快照支撑项目结论。这样的框架更适合顶级奖项答辩，因为它能同时服务评审、答辩人和开发维护者。")
    add_table(doc, ["参考对象", "链接", "本文吸收的写法"], REFERENCE_LINKS, [2300, 3300, 3760])

    add_heading(doc, "项目总览图", 1)
    add_code_block(doc, "\n".join(ARCHITECTURE_LINES))

    add_heading(doc, "赛题得分点总映射", 1)
    add_table(doc, ["得分点", "实现位置", "说明"], REQUIREMENT_TABLE, [2100, 2600, 4660])

    for idx, (chapter, sections) in enumerate(CHAPTERS, 1):
        add_heading(doc, f"第{idx}章 {chapter}", 1)
        add_para(doc, CHAPTER_INTROS[chapter])
        for paragraph in CHAPTER_DEEP_DIVES[chapter]:
            add_para(doc, paragraph)
        for sec_idx, (section_title, tag, idea, implementation, operation) in enumerate(sections, 1):
            add_heading(doc, f"{idx}.{sec_idx} {section_title}", 2)
            for paragraph in section_paragraphs(section_title, tag, idea, implementation, operation):
                add_para(doc, paragraph)
            if section_title in {"核心评价指标", "测试、验证与质量保障"}:
                add_table(doc, ["证据项", "当前结果", "意义"], EVIDENCE_TABLE, [2200, 1700, 5460])
            if section_title in {"功能操作指南", "Readiness 操作", "安装与基础检查"}:
                add_table(doc, ["操作", "命令", "用途"], COMMAND_TABLE, [1700, 4300, 3360])

    add_heading(doc, "附录 A 常用命令速查", 1)
    add_table(doc, ["操作", "命令", "用途"], COMMAND_TABLE, [1700, 4300, 3360])

    add_heading(doc, "附录 B 关键证据摘要", 1)
    add_table(doc, ["证据项", "当前结果", "意义"], EVIDENCE_TABLE, [2200, 1700, 5460])
    for title, paragraphs in APPENDIX_SECTIONS:
        add_heading(doc, title, 2)
        for paragraph in paragraphs:
            add_para(doc, paragraph)

    add_heading(doc, "附录 C 参考资料", 1)
    for name, url, note in REFERENCE_LINKS:
        add_no_indent_para(doc, f"{name}：{url}。{note}")

    doc.save(OUTPUT)
    md = write_markdown()
    SOURCE_MD.write_text(md, encoding="utf-8")
    return OUTPUT, count_chinese_chars(md)


if __name__ == "__main__":
    output, chars = build_docx()
    print(f"Wrote: {output}")
    print(f"Chinese character count in source markdown: {chars}")
