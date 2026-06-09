# FinDSL Forge 赛题 19 答辩 PPT 说明

本目录保存 FinDSL Forge 项目的中文答辩展示稿、预览图、PPT 源模块、图片资产和数据说明。

## 最终文件

- PPTX：`output/FinDSL-Forge-赛题19答辩展示稿.pptx`
- 预览联系表：`preview/contact-sheet.png`
- 每页预览：`preview/slide-01.png` 至 `preview/slide-24.png`
- 构建脚本：`../../../../scripts/build_findsl_defense_ppt.py`

## 内容结构

本次生成的 PPT 共 24 页，面向赛题 19“行情选股 DSL 到高性能 Doris SQL 的自动化编译系统”答辩使用。内容按“赛题问题、方案定位、核心编译链路、Doris 性能证据、正确性验证、数据治理、风险边界、交付回溯、答辩准备”展开。

## 数据来源

关键指标来自项目当前的 `submission_artifacts/evidence_metadata.json`：

- Pytest：203 passed in 13.11s；
- 官方风格正例：37/37；
- 官方风格负例：37/37；
- Blocking gates：PASS；
- Warning count：0；
- Doris evidence：PASS；
- Doris speedup：36.24x；
- Baseline 平均执行时间：5182.04 ms；
- Optimized 平均执行时间：142.99 ms；
- Doris 行数一致：88586 / 88586。

## 图片与图表说明

- `assets/imagegen_*.png`：使用 Codex 内置 `imagegen` 生成的无文字概念底图，提示词组织参考 GPT-Image2-Skill。它们只用于视觉表达，不作为真实运行证据。
- `assets/01_*.png` 至 `assets/10_*.png`：此前整理的中文准确版 AI 概念图，用于章节视觉和答辩说明。
- `assets/chart_*.png`：用项目真实 evidence metadata 通过 Matplotlib 生成的科研图风格数据图，数值来自项目证据文件。
- PPT 中标题、指标、表格、流程框和讲稿均为 PPT 可编辑文本/对象，方便后续人工修改。

## 重新生成

在项目根目录运行：

```powershell
python scripts\build_findsl_defense_ppt.py
```

脚本会重新复制图片资产、生成科研图、生成 24 个 slide module，并调用 artifact-tool 导出 PPTX 和预览图。Windows 下 artifact-tool 有时会在成功写出文件后返回非零退出码，脚本已做文件存在性校验，只要 PPTX 和联系表非空就继续。

## 使用提醒

答辩时不要把 AI 概念图说成真实截图。真实运行、测试、Doris、Git、提交包核验证据，应使用项目截图证据包、`submission_artifacts`、`reports` 和终端复现结果。
