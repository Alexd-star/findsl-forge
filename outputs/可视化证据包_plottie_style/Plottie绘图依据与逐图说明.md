# Plottie 绘图依据与逐图说明

本轮重写删除了旧单体绘图脚本，改为按图类拆分代码。Plottie 的作用是提供论文图型检索和视觉语法参考：不同证据类型对应不同图型，而不是把所有内容塞进同一种 dashboard 模板。

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

## 图类规则

| 图类 | 代码文件 | 采用规则 |
|---|---|---|
| flow | `scripts/plottie_figures/flow.py` | 用细线、短标签和单一主色表达过程，不用 UI 卡片、阴影或图标堆叠。 |
| network | `scripts/plottie_figures/network.py` | 用节点、边和分层坐标表达依赖关系，直接标注，避免彩色系统大屏风格。 |
| matrix | `scripts/plottie_figures/matrices.py` | 状态、门禁和要求对应关系用矩阵/棒棒糖/紧凑表格表达，不做仪表盘。 |
| performance | `scripts/plottie_figures/performance.py` | 延迟和加速比用 log-scale range/dot plot 表达，保留数据来源和未重测边界。 |
| image_plate | `scripts/plottie_figures/image_plates.py` | 实际截图按 image plate 排版，只加细边框和 panel label，不合成假界面。 |

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
