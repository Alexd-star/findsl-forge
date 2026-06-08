# 赛题 19 完成度与下一步规划

## 1. 状态汇总

| 状态 | 数量 | 含义 |
|---|---:|---|
| implemented | 8 | 已有代码、测试或证据支撑。 |
| partial | 2 | 主干可用，但仍有边界或模板化空间。 |
| needs_evidence | 2 | 依赖官方数据、现场 Doris 或更多 benchmark 证据。 |

## 2. 官方要求逐项复核

| 编号 | 要求 | 状态 | 当前证据 | 下一步 |
|---|---|---|---|---|
| T19-R1 | DSL 到高性能 Doris SQL 自动化编译系统 | implemented | Compiler.compile、SqlGenerator.generate、DORIS_SQL_VALIDATION 已形成主链路。 | 继续用官方新增问句扩充 official suite。 |
| T19-R2 | 自然语言转 DSL 后的最后一公里执行 | implemented | NL2DSL/LLM 候选均进入确定性编译与验证，不允许直接 SQL 绕过。 | 真实 provider 演示前保存原始响应和验证截图。 |
| T19-R3 | then、CONS/EXIST、跨市场位运算、强类型约束、标准 AST | implemented | parser、semantic、AST、official suite 覆盖主干复合语义。 | 拿到官方 DSL 规范后逐条补充 12 类函数隐藏样例。 |
| T19-R4 | ANTLR4 或同类工具、BNF、全量 12 类领域函数 | partial | 当前使用递归下降 parser，同类解析能力可测；配置函数数 14。 | 若发榜单位强制 ANTLR4，迁移文法层；否则补充 BNF 与 12 类函数对照表。 |
| T19-R5 | CTE 嵌套与窗口函数自动化生成 | implemented | then 生成 staged CTE，MA/SUM/MAX/MIN/CONS/EXIST/RET 生成窗口或特征层。 | 继续补多层 then + rank + date window 的官方压力样例。 |
| T19-R6 | 业务规则与编译内核解耦 | implemented | indicators/tables/functions 三类配置由 Registry 加载，新增 ABS 模板函数证明函数模板扩展路径。 | 将官方复权、指数不复权和成分股规则继续配置化。 |
| T19-R7 | 19 年以上长周期查询自动路由到前缀和、物化视图或分区裁剪 | needs_evidence | 已有 5M Doris、120 日成交量 prefix-sum 36.24x 证据；物化视图和更多指标路径需补证据。 | 拿官方 20 年数据后重跑 Doris benchmark，按函数/窗口生成性能矩阵。 |
| T19-R8 | SQL 正确率 >= 95% | implemented | pytest、official positive/negative、SQL/reference equivalence 构成正确性证据。 | 官方隐藏问句到位后补入 official suite 并更新 evidence summary。 |
| T19-R9 | 新指标/新函数 0 行核心代码改动 | partial | 新指标配置化已实现；ABS 证明简单 numeric scalar 函数可通过配置模板扩展。 | 复杂时序函数仍需模板协议升级，不能在答辩中夸大为任意函数零代码。 |
| T19-R10 | 编译 P95 < 50ms | implemented | readiness 统计 compile P95，证据快照低于 50ms。 | 每次扩展 parser/sqlgen 后重新跑 readiness。 |
| T19-R11 | SQL 执行筛选结果不高于 10s | needs_evidence | 当前 Doris 证据中特定优化路径远低于 10s。 | 用官方全量问句和官方数据生成逐问句执行时间表。 |
| T19-R12 | Markdown 表格、工程效果图、可运行项目成果与技术文档 | implemented | submission_artifacts、docs、导师文档、Demo 截图和视频脚本已有体系。 | 最终提交前按组委会模板补精益画布、原创性声明和每目录 readme.txt。 |

## 3. 下一步开发规划

第一优先级是把官方 DSL 规范拿到后做逐项函数清单。当前项目已经覆盖主要函数族，但官方题面只写“12 类领域函数”，没有在 TXT 中展开完整清单，所以不能凭猜测宣称全量闭环。

第二优先级是继续增强函数模板协议。当前 ABS 证明了简单数值标量函数可以通过 `functions.json` 的 `sql_template` 和 `reference_op` 进入 SQL 生成和 reference 验证；后续复杂时序函数应扩展为窗口模板、布尔模板和聚合模板。

第三优先级是官方数据到位后重跑 Doris 证据。需要按官方问句生成 baseline/optimized SQL、行数一致性、P50/P95/平均耗时和 10s 达标表。没有官方数据时，只能把现有 5M Doris 证据作为长窗口核心路径证明。

第四优先级是提交包格式。按参赛指南补齐精益画布、原创性声明、文件夹 `readme.txt`、统一模板 PPT 和 1 分钟视频，保证可运行测试之外的材料不丢分。