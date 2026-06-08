# FinDSL Forge 可视化截图证据包

本目录由 `scripts/build_visual_evidence.py` 生成，用于项目验收、答辩、审计和最终提交核验。

生成时间：2026-06-08 16:40:03 +0800

## 目录说明

| 目录 | 说明 |
|---|---|
| `screenshots/` | PNG 截图文件，包含命令日志渲染截图、Web Demo 实际界面截图、既有 Demo 截图副本 |
| `logs/` | 每张终端类截图对应的原始命令输出，便于复核 |
| `html/` | 截图渲染用 HTML 和 Playwright 临时脚本 |
| `generated_outputs/` | 本次运行生成的 JSON/Markdown 样例输出、benchmark 输出和 API 输出 |
| `SCREENSHOT_EVIDENCE_INDEX.md` | 完整中文截图清单、通过标准、不适用说明和执行顺序 |

## 取证原则

终端类截图不是手写图片，而是先运行真实命令，将 stdout/stderr、退出码、工作目录和耗时保存为原始日志，再渲染成 PNG。Web 类截图来自实际启动的本地 Demo 服务。无法由当前项目真实产生的内容，例如比赛平台上传成功、模型权重文件、未启动时的现场 Doris 连接，均在索引中标注为“不适用”或“待人工补拍”。

## 当前数量

- 已登记证据项：70
- 已补齐或有截图证据项：65
- 不适用或待人工补拍项：6

建议先打开 `SCREENSHOT_EVIDENCE_INDEX.md`，按“最终截图执行顺序”复核，再从 `screenshots/` 目录挑选提交材料和答辩 PPT 所需图片。
