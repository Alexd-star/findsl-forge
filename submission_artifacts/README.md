# 当前证据包

本目录只保存可随源码回溯的当前评分证据。`reports/` 是本地生成区，默认不进入 Git；PPT、长篇手册、截图和视频在功能封板后单独生成，也不进入日常源码版本。

| 文件 | 作用 |
| --- | --- |
| `evidence_metadata.json` | 机器可读的门禁、正确率、性能、Git 和数据身份 |
| `evidence_summary.md` | 从 metadata 自动生成的摘要 |
| `evidence_manifest.md` | 当前快照文件和导出环境清单 |
| `evidence_snapshots/` | 正确率、性能、Doris、水位、语料覆盖和数据缺口证据 |

重新导出：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

导出脚本使用白名单，不再复制旧阶段的全部中间报告。证据合同失败时必须修复来源，不得手工篡改 PASS 状态。

当前快照基线是 Git `414a980`。后续仓库整理提交不改变该次 Doris 实验事实；最终提交前仍需在冻结功能后的新基线上完整重采。
