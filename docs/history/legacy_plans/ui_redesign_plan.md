# FinDSL Forge Web Demo UI 改造规划

## 1. 改造目标

FinDSL Forge Web Demo 的目标不是做一个通用后台系统，而是做一个面向评审、答辩和项目交接的“可解释编译驾驶舱”。页面需要在有限时间内讲清楚四件事：用户输入的中文需求如何变成受控 DSL，DSL 如何经过确定性编译生成 Doris SQL，结果如何通过 SQL/reference 等价验证，Doris 规模证据如何支撑性能结论。

当前 Demo 已经具备完整功能，但视觉层次偏基础，信息密度和答辩叙事还可以增强。改造后的页面应让评委一眼看到“不是 LLM 直接写 SQL，而是 DSL 编译器 + 验证器 + Doris evidence”的主线。界面要稳重、清晰、适合金融科技比赛，不做营销式 hero，也不做装饰性大图。

## 2. 外部参考与架构选择

本次参考三类优秀前端实践：

1. shadcn/ui dashboard block：其 dashboard block 采用 app sidebar、site header、section cards、chart/data table 的组合方式，适合构建信息密集的工具型界面。参考重点是“应用壳 + 状态摘要 + 内容区域组件拆分”，不是引入 React 或 Tailwind。
2. Observable Framework：其定位是用代码构建快速、漂亮的数据应用和报告，强调 Markdown、JavaScript、SQL/Python 数据加载和可复现文件结构。参考重点是“数据证据可读、报告和交互输入结合”，与本项目 evidence 展示目标一致。
3. Ant Design Pro：其企业后台经验适合参考稳定、可扫描、任务导向的页面组织。参考重点是“顶部状态、工作区、表格/详情、错误反馈”，不是套用完整 Ant Design 技术栈。

项目当前没有前端构建链，`pyproject.toml` 也保持零运行依赖。为避免增加 npm、Node、打包、CI 和提交包复杂度，本次选择“原生 HTML/CSS/JS 高质量重构”的最佳实践：保留 Python `http.server` 单文件返回页面，前端使用 CSS 变量、语义化 DOM、原生 fetch、状态管理函数和响应式布局完成升级。

## 3. 设计原则

页面设计采用“金融工程控制台”方向。视觉应像一套给评审看的分析系统，而不是宣传页。整体使用浅色工作台、深色代码区、克制的青绿色强调色和少量琥珀色风险提示。信息密度要高，但不能拥挤；标题、状态、指标和代码输出要有明显层级。

界面不使用紫色渐变、玻璃拟态、巨大圆角、重复卡片堆叠或装饰性背景。按钮和标签用清晰动词与状态词，例如“Suggest DSL”“Run analysis”“Copy SQL”。状态反馈要明确区分 passed、diagnostic、error、running 和 waiting。

## 4. 信息架构

改造后的页面分为五个区域：

1. 顶部应用栏：展示项目名称、当前状态、Doris evidence 关键速度指标、提交门禁提示。
2. 左侧输入工作区：包含中文需求、候选 DSL、样例选择、DSL 编辑器、Prefix/Verify 开关和运行按钮。
3. 右侧结果工作区：包含关键指标卡、SQL/AST/Explain/Rows/Evidence/Diagnostic 标签页和复制按钮。
4. Explain 时间线：把 optimizer explain 从纯 JSON 转成可扫描的 rule/status/evidence 列表。
5. Evidence 摘要：展示 Doris speedup、baseline/optimized latency、row count match、报告路径和证据状态。

## 5. 组件划分

虽然当前仍是单文件 HTML，但代码会按组件职责组织：

- Layout：`app-shell`、`topbar`、`workspace-grid`。
- Inputs：`nlInput`、`candidateList`、`exampleSelect`、`dslInput`、`toggles`。
- Status：`buildState`、`metricStatus`、`metricLatency`、`metricRows`、`metricPrefix`、`metricEvidence`。
- Output：`tabs`、`outputPane`、`errorBox`、`copyButton`。
- Render helpers：`renderSql`、`renderAst`、`renderExplain`、`renderRows`、`renderEvidence`、`renderDiagnostic`。
- API helpers：`loadExamples`、`loadEvidence`、`suggest`、`run`。

## 6. 交互改造

页面加载后仍自动执行默认中文需求，但状态展示要更清楚。候选 DSL 以列表显示，每个候选展示规则、置信度、验证状态和 DSL 文本。用户点击候选后，可自动填入 DSL 并运行。

样例选择将保留 baseline、official positive、official negative、real market 四类。负例应自动关闭 verify，运行后展示稳定诊断码、期望诊断码、实际诊断码和修复建议。真实行情样本应在状态区显示 Eastmoney sample，避免和 5M Doris 性能证据混淆。

输出区域不再只用一个大 `pre` 承载所有内容。SQL 和 AST 可以继续用代码块；Explain、Rows、Evidence、Diagnostic 应使用结构化视图。这样更适合截图和现场讲解。

## 7. 验证计划

改造完成后必须验证：

1. `python -m pytest tests/test_demo.py -q`
2. `python -m pytest -q`
3. 启动 `scripts/serve_demo.ps1`
4. 用浏览器或 Playwright 打开 `http://127.0.0.1:8765`
5. 检查默认中文需求、官方正例、真实行情样本、UNKNOWN_INDICATOR 负例
6. 截图确认桌面宽度和移动宽度不重叠、不溢出、不空白
7. 若截图内容变化明显，刷新 `submission_artifacts/demo_screenshots`

## 8. 首轮实施范围

首轮只改 Web Demo 页面，不改编译器、验证器、Doris evidence、CLI 和后端 API 协议。这样可以控制风险，保证 readiness 不受 UI 改造影响。

首轮完成后，Web Demo 应达到可用于正式答辩截图和现场演示的水平。后续若仍有时间，再考虑把 HTML/CSS/JS 从 `demo.py` 拆分为静态资源文件，或补充演示模式、快捷键和更完整截图自动化。
