# 最终证据生成说明

动态评分证据不再提交进源码仓库，避免证据归档本身改变 Git HEAD，或历史快照与当前代码混用。最终交付采用冻结发布流程：

```powershell
pwsh -File .\scripts\refresh_final_evidence.ps1
pwsh -File .\scripts\build_submission_package.ps1
```

第一条命令在同一 Git HEAD 与同一 Doris 数据快照上重采源码质量、正确率、执行性能、长周期加速、编译延迟、12 类函数能力、配置式扩展和复杂查询证据。第二条命令通过 `git archive` 导出源码，只复制白名单证据和产品截图，排除依赖环境、缓存、日志、数据库文件、本机绝对路径及敏感配置，并生成逐文件 SHA-256 清单和最终 ZIP。

生成结果位于 `final_submission/`，该目录默认不进入 Git。上传前以包内 `03_提交说明/PACKAGE_VERIFICATION.md` 的 `PASS` 为准。
