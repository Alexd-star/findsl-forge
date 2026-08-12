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

当前快照绑定核心代码提交 Git `a531f1c`，证据合同、数据指纹、正确率和性能报告已统一重采并通过。其后的证据归档提交只包含文档与快照，不改变该核心代码树。
