# FinDSL Forge 一分钟答辩视频脚本

本脚本配合 `scripts/build_defense_video.py` 使用。视频以 `submission_artifacts/demo_screenshots/` 中的七张截图为素材，合成约 60 秒 MP4。成片默认没有录入人声，但每一页已带中文字幕；正式提交或路演时，可以按下面讲稿补录旁白。

## 生成命令

```powershell
$env:PYTHONPATH="src"
python scripts\build_defense_video.py
```

生成文件：

`submission_artifacts/defense_video/findsl_forge_one_minute_demo.mp4`

## 时间轴与旁白

| 时间 | 画面 | 旁白 |
|---|---|---|
| 00:00-00:07 | 中文请求与候选 DSL | FinDSL Forge 的入口是中文选股请求，但系统不会让模型直接写 SQL。中文只生成候选 DSL，后面所有动作都要经过确定性编译器验证。 |
| 00:07-00:16 | Doris SQL 标签页 | 这一步展示的是编译结果。页面能看到验证通过、毫秒级编译延迟、结果行数，以及可审计的 Doris SQL。 |
| 00:16-00:23 | AST 标签页 | AST 说明系统理解了表达式结构，能区分 filter、连续条件、指标和排名，不是靠字符串模板硬拼。 |
| 00:23-00:31 | Explain 标签页 | 编译器会记录 explain，评委可以追踪日期裁剪、窗口处理和 prefix-sum 选择，优化不是黑盒。 |
| 00:31-00:38 | Rows 标签页 | SQL 执行结果还会和 Pandas reference 做等价校验。金融系统不能只看 SQL 长得对，还要证明语义结果一致。 |
| 00:38-00:48 | Evidence 标签页 | Doris 规模证据使用 5,000,000 行数据，baseline 和 optimized 行数一致，prefix 路径达到 36.24x 加速，超过 10x 目标。 |
| 00:48-01:00 | 负例诊断 | 最后展示错误输入。未知指标不会进入 SQL 执行，而是返回稳定诊断码和修复建议，证明系统能优雅失败。 |

## 录制建议

正式录制人声时，语速保持每分钟 210 到 240 个汉字左右。不要逐字念页面字幕，重点讲清楚六件事：中文入口、确定性编译、AST 结构、可解释优化、独立验证、Doris 规模证据和负例诊断。

如果比赛平台要求真人录屏，可以先播放生成的 MP4，再用系统录屏工具录入旁白；如果平台接受无声视频，则直接提交生成文件和本脚本即可。
