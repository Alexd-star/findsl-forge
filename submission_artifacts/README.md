# FinDSL Forge 提交包导览

本目录用于放置可随代码一起提交和回溯的轻量交付材料。`reports/` 目录是本地生成目录，默认被 `.gitignore` 忽略；最终提交前请运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

脚本会把当前 readiness、Doris 证据、官方风格套件、答辩包等报告复制到 `submission_artifacts/evidence_snapshots/`，避免评审材料只停留在本机临时报告中。

## 推荐提交顺序

1. 运行 `scripts/submission_readiness.ps1`，确认 blocking gates 通过、warning 为 0。
2. 如果需要重做 5M Doris 证据，运行 `scripts/prepare_doris_scale_evidence.ps1`。
3. 运行 `scripts/export_submission_artifacts.ps1` 导出证据快照。
4. 按 `demo_script.md` 做一次完整演练。
5. 结合 `demo_screenshots/` 中的截图制作正式 PPT 或录屏讲解稿。

## 交付物地图

| 文件 | 用途 |
|---|---|
| `technical_report.md` | 技术报告正文骨架，覆盖问题、方案、架构、实验、创新点 |
| `score_mapping.md` | 赛题得分点到实现和证据的映射 |
| `demo_script.md` | 现场演示脚本和故障兜底顺序 |
| `defense_ppt_outline.md` | 答辩 PPT 逐页内容 |
| `defense_video_script.md` | 一分钟答辩视频时间轴、旁白和生成命令 |
| `real_data_ingestion_plan.md` | 真实行情数据接入方案 |
| `evidence_snapshots/` | 从 `reports/` 导出的可版本化证据快照 |
| `demo_screenshots/` | Web Demo 正例、SQL、AST、Explain、Rows、Evidence 和负例诊断截图 |
| `defense_video/` | 由截图合成的一分钟答辩视频输出目录 |

## 当前核心证据口径

- 编译正确性：官方风格正例、负例、SQL/reference 等价验证。
- 安全性：LLM 候选必须经过 DSL 编译器验证，直接 SQL 和错误 DSL 会被拒绝。
- 性能：Doris 5,000,000 行真实集群执行证据，baseline window 与 prefix-sum 优化路径结果一致，优化加速超过 10x。
- 展示：Web Demo 截图已进入 `submission_artifacts/demo_screenshots/`，覆盖正例全链路和负例诊断。
- 视频：`scripts/build_defense_video.py` 可从截图生成一分钟 MP4，`defense_video_script.md` 提供旁白口径。
- 可回溯：代码进入 Git；报告快照进入 `submission_artifacts/`；大规模 CSV 由脚本可重建，不进入 Git。
