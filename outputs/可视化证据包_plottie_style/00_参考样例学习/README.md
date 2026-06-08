# 参考样例学习包

本目录用于记录本轮重画前实际查看过的参考项目样例。它不是项目成果图，也不建议作为最终提交图件；作用是说明本项目图表的版式、配色、线宽、图例和导出规则来自哪些已安装参考项目。

样例接触表：`outputs\可视化证据包_plottie_style\00_参考样例学习\reference_examples_contact_sheet.png`

## 参考样例

| 编号 | 项目 | 样例 | 源文件/脚本 | 预览 | 学到的绘图规则 | 应用到本项目 |
|---|---|---|---|---|---|---|
| REF-01 | figures4papers | speed comparison panel | `external_references/scientific_figure_code/figures4papers/figure_RNAGenScape/figures/results_comparison_speed.png` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-01_figures4papers_preview.png` | wide comparison panel, direct numeric annotations, semantic blue for the key method | FIG-09 Doris latency/speedup and matrix/performance panels |
| REF-02 | figures4papers | composition heatmap | `external_references/scientific_figure_code/figures4papers/figure_ophthal_review/figures/composition_heatmap.png` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-02_figures4papers_preview.png` | compact matrix with cell annotations, quiet axes and one continuous color scale | FIG-08 plan comparison, FIG-10 validation matrix, FIG-11 compliance matrix |
| REF-03 | figures4papers | method schematic | `external_references/scientific_figure_code/figures4papers/assets/ImmunoStruct_schematic.png` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-03_figures4papers_preview.png` | schematic-first method panel with small supporting panels and consistent panel labels | FIG-01, FIG-02, FIG-06, FIG-07, FIG-12 and FIG-14 |
| REF-04 | Show2Know | confidence interval line | `external_references/scientific_figure_code/Show2Know/2 Line Plot/95ConfidenceInterval/draw_95_CI.py` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-04_Show2Know_preview.png` | line or dot estimates with uncertainty bands instead of isolated metric cards | FIG-09 paired range plot and performance annotation strategy |
| REF-05 | Show2Know | multi-line fill | `external_references/scientific_figure_code/Show2Know/15 Multi-Line-With-Fill/run.py` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-05_Show2Know_preview.png` | thin line plus low-alpha interval fill, with restrained legend use | performance-family charts where intervals or paired comparisons are needed |
| REF-06 | Show2Know | multi-image plate | `external_references/scientific_figure_code/Show2Know/14 Multi-Image-To-One/run.py` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-06_Show2Know_preview.png` | image plate assembly with consistent tile geometry and minimal captions | FIG-15 Web Demo image evidence plate |
| REF-07 | nature-skills | heatmap atlas | `external_references/scientific_figure_code/nature-skills/skills/nature-figure/assets/chart-atlas/atlas-03-heatmaps.png` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-07_nature-skills_preview.png` | multi-panel matrix atlas, tight gutters, no decorative containers | matrix charts and requirement/evidence maps |
| REF-08 | nature-skills | forest and interval atlas | `external_references/scientific_figure_code/nature-skills/skills/nature-figure/assets/chart-atlas/atlas-07-forest-interval.png` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-08_nature-skills_preview.png` | interval/dot estimates as evidence, using the axis rather than dashboard badges | FIG-09 latency and speedup evidence |
| REF-09 | nature-skills | Nature-style mechanism gallery | `external_references/scientific_figure_code/nature-skills/skills/nature-figure/assets/gallery/fig1-material-mechanism-rich.png` | `outputs\可视化证据包_plottie_style\00_参考样例学习\REF-09_nature-skills_preview.png` | one visual claim per panel, lowercase panel labels, restrained supporting plots | all generated figures as the final QA target |

## 抽取后的统一规则

1. 采用最终论文尺寸绘制，不做网页大屏比例。
2. 定量图优先使用点图、区间图、矩阵图和 log-scale range plot，不使用指标卡、饼图、3D 图或无来源曲线。
3. 主色采用 figures4papers 的深蓝，辅助色采用 Show2Know 低饱和论文配色，红/橙仅用于风险、阈值或边界。
4. SVG/PDF 保持文字可编辑；PNG 用于预览；TIFF 用于高分辨率归档；灰度版用于检查脱离颜色后仍可阅读。
5. 真实截图只做 image plate 编排，不重绘、不美化成虚假界面。
