# Plottie 绘图依据与逐图说明

本轮重写删除了旧单体绘图脚本，改为按图类拆分代码。Plottie 的作用是提供论文图型检索和视觉语法参考：不同证据类型对应不同图型，而不是把所有内容塞进同一种 dashboard 模板。

本轮同时安装并核验 figures4papers、Show2Know 和 nature-skills；参考样例接触表见：`outputs\可视化证据包_plottie_style\00_参考样例学习\reference_examples_contact_sheet.png`。

## 外部参考

| 来源 | 用途 |
|---|---|
| [Plottie scientific plot atlas](https://plottie.art/) | 图型分类、配色、尺寸或导出参考 |
| [Plottie collections](https://plottie.art/collections) | 图型分类、配色、尺寸或导出参考 |
| [Plottie palettes](https://plottie.art/palette) | 图型分类、配色、尺寸或导出参考 |
| [Plottie line plots](https://plottie.art/plots/line-plots) | 图型分类、配色、尺寸或导出参考 |
| [Plottie scatter plots](https://plottie.art/plots/scatter-plots) | 图型分类、配色、尺寸或导出参考 |
| [Plottie heatmaps](https://plottie.art/plots/heatmaps) | 图型分类、配色、尺寸或导出参考 |
| [Plottie volcano plots guide](https://plottie.art/plots/volcano-plots) | 图型分类、配色、尺寸或导出参考 |
| [Nature building and exporting panels](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/) | 图型分类、配色、尺寸或导出参考 |
| [Nature figure specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/) | 图型分类、配色、尺寸或导出参考 |
| [Matplotlib customizing and export](https://matplotlib.org/stable/users/explain/customizing.html) | 图型分类、配色、尺寸或导出参考 |

## 已安装 GitHub 参考项目

| 项目 | 本地路径 | HEAD | 安装核验 | 应用方式 |
|---|---|---|---|---|
| [figures4papers](https://github.com/ChenLiu-1996/figures4papers) | `external_references/scientific_figure_code/figures4papers` | `ce567dd` | PASS | GridSpec multi-panel composition, direct labelling, semantic palette and vector export helpers |
| [Show2Know](https://github.com/Winn1y/Show2Know) | `external_references/scientific_figure_code/Show2Know` | `40f33d1` | PASS | paper color temple, heatmap/matrix recipes, line/range plot patterns and multi-image plate layout |
| [nature-skills](https://github.com/Yuan1z0825/nature-skills) | `external_references/scientific_figure_code/nature-skills` | `6f1a944` | PASS | Nature figure contract, backend exclusivity, QA checklist, editable SVG/PDF and image integrity rules |

## 已查看参考样例

| 编号 | 项目 | 样例 | 学到的规则 | 应用到本项目 |
|---|---|---|---|---|
| REF-01 | figures4papers | speed comparison panel | wide comparison panel, direct numeric annotations, semantic blue for the key method | FIG-09 Doris latency/speedup and matrix/performance panels |
| REF-02 | figures4papers | composition heatmap | compact matrix with cell annotations, quiet axes and one continuous color scale | FIG-08 plan comparison, FIG-10 validation matrix, FIG-11 compliance matrix |
| REF-03 | figures4papers | method schematic | schematic-first method panel with small supporting panels and consistent panel labels | FIG-01, FIG-02, FIG-06, FIG-07, FIG-12 and FIG-14 |
| REF-04 | Show2Know | confidence interval line | line or dot estimates with uncertainty bands instead of isolated metric cards | FIG-09 paired range plot and performance annotation strategy |
| REF-05 | Show2Know | multi-line fill | thin line plus low-alpha interval fill, with restrained legend use | performance-family charts where intervals or paired comparisons are needed |
| REF-06 | Show2Know | multi-image plate | image plate assembly with consistent tile geometry and minimal captions | FIG-15 Web Demo image evidence plate |
| REF-07 | nature-skills | heatmap atlas | multi-panel matrix atlas, tight gutters, no decorative containers | matrix charts and requirement/evidence maps |
| REF-08 | nature-skills | forest and interval atlas | interval/dot estimates as evidence, using the axis rather than dashboard badges | FIG-09 latency and speedup evidence |
| REF-09 | nature-skills | Nature-style mechanism gallery | one visual claim per panel, lowercase panel labels, restrained supporting plots | all generated figures as the final QA target |

## 图类规则

| 图类 | 代码文件 | 采用规则 |
|---|---|---|
| flow | `scripts/plottie_figures/flow.py` | 用 nature-skills 的 method schematic 约束和 figures4papers 的 GridSpec/直接标注方式表达过程，不用 UI 卡片、阴影或图标堆叠。 |
| network | `scripts/plottie_figures/network.py` | 用 figures4papers 的分层/网络示意写法表达依赖关系，采用 Show2Know 低饱和配色作极少量强调，避免彩色系统大屏风格。 |
| matrix | `scripts/plottie_figures/matrices.py` | 参考 Show2Know heatmap 和 figures4papers validation panel，把状态、门禁和要求对应关系画成矩阵/棒棒糖/紧凑表格，不做仪表盘。 |
| performance | `scripts/plottie_figures/performance.py` | 结合 Show2Know line/errorbar 思路和 figures4papers comparison panel，把延迟和加速比画成 log-scale range/dot plot，保留未重测边界。 |
| image_plate | `scripts/plottie_figures/image_plates.py` | 参考 Show2Know Multi-Image-To-One 与 nature-skills image integrity，实际截图只做 image plate 排版，不合成假界面。 |

## 逐图结论

| 图号 | 结论 | 证据来源 |
|---|---|---|
| FIG-01 | 赛题任务可以被拆成输入、编译、验证、性能和交付五条证据线。 | README + topic compliance |
| FIG-02 | 自然语言候选必须被确定性编译器和 reference oracle 复核后才能形成 Doris SQL。 | README + compiler reports |
| FIG-03 | 项目由入口、适配、编译、配置、验证和证据交付六层组成。 | PROJECT_INDEX + src |
| FIG-04 | CLI 把编译、验证、官方套件、Demo 和证据导出统一到同一链路。 | src/findsl |
| FIG-05 | 验收应从环境、命令、测试、证据到提交状态逐层收口。 | SCREENSHOT_EVIDENCE_INDEX |
| FIG-06 | FinDSL 先形成 typed AST，再生成可验证的 Doris-safe SQL。 | compiler.py + parser.py + semantic.py |
| FIG-07 | 滚动 SUM 在满足条件时可改写为 prefix-table 访问，并保留窗口函数回退路径。 | sqlgen.py + Doris evidence |
| FIG-08 | 优化路径把运行时窗口聚合替换为 prefix-table predicate 与 join。 | doris_cluster_evidence |
| FIG-09 | 冻结 Doris evidence 显示 prefix-sum 路径达到 36x 级延迟下降。 | doris_cluster_evidence.json |
| FIG-10 | 最新证据显示 required gates 全通过，warning count 为 0。 | evidence_metadata.json |
| FIG-11 | 已实现、部分实现和待补证据必须如实分开表达。 | topic_19_compliance_plan.md |
| FIG-12 | LLM 只产生候选 DSL，执行权由编译器和验证器控制。 | llm_adapter.py + readiness |
| FIG-13 | 指标、函数和表配置通过 Registry 同时服务语义、SQL、reference 与测试。 | configs + registry |
| FIG-14 | Doris 证据从 DDL、prefix 表、采集脚本进入 evidence snapshot。 | deploy/doris + evidence |
| FIG-15 | Demo 截图应作为真实图像证据板展示，不重绘、不伪造、不遮挡状态。 | actual screenshots |
| FIG-16 | 最终交付物围绕源码、配置、数据、测试、文档和 evidence snapshots 组织。 | PROJECT_INDEX + evidence_manifest |
| FIG-17 | 真实行情样本证明语义可信性，5M Doris evidence 证明规模性能，两者不能混为同一数据集。 | real samples + Doris evidence |
