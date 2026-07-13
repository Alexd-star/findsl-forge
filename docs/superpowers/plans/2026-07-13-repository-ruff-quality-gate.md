# 全仓 Ruff 静态质量门禁治理

## 1. 治理目标

此前项目的阶段代码均执行定向 Ruff，但对整个仓库运行 `python -m ruff check .` 会报告 214 条问题。企业级交付不能用局部检查代替全仓检查，也不能为了得到绿色结果粗暴关闭规则。本轮按文件所有权和问题性质分类，先隔离不可手工维护的生成物，再修复真实源码。

## 2. 基线分类

初始 214 条问题由以下部分构成：

- ANTLR 自动生成的 Lexer、Parser、Visitor：95 条；
- 包级 `__init__.py` 公共 API 重导出：83 条；
- 实际源码、文档生成脚本和测试：36 条。

ANTLR 文件由语法和生成器决定，直接修改会在下一次生成时丢失，因此在 Ruff 的精确目录排除项中管理。`__init__.py` 使用 wildcard 或显式重导出构成稳定公共 API，只对这些文件忽略 `F401/F403/F405`，不影响普通模块。绘图入口在设置仓库路径后导入本地包，只对该单文件忽略 `E402`。

## 3. 实际修复

剩余真实问题没有通过全局 ignore 隐藏。机械修复包括未使用的类型、文档库、绘图常量和测试导入，以及无占位符 f-string。人工修复包括：

- 删除三处已经由 `_count_rule_predicate_sql` 接管的冗余 threshold 变量；
- 保留两处仍直接进入 SQL 文本的 threshold，防止误删造成运行期未定义变量；
- 将参考执行器中的 `l/r` 比较参数改为可读名称；
- 删除滚动参考实现中未使用的 pandas 局部别名；
- 删除答辩图脚本中未参与绘图的数据数组。

这些改动不改变 DSL 语义、SQL 结构、Doris 计划或测试预期。针对官方槽位、参考执行器、文档/绘图脚本导入、领域注册表和 readiness 的测试均通过。

## 4. 持续门禁

开发依赖固定加入 `ruff==0.15.13`，避免本地与 CI 使用不同规则版本。GitHub Actions 顺序调整为：安装开发依赖、校验 ANTLR 生成源、全仓 Ruff、全量 pytest。任何普通源码新增未使用导入、未定义变量或歧义变量名都会阻止合并。

最终验证命令：

```powershell
python -m ruff check .
python scripts/generate_antlr.py --check
powershell -ExecutionPolicy Bypass -File scripts/submission_readiness.ps1
```

当前结果为全仓 Ruff `0` 条、ANTLR 生成源一致、pytest `876 passed`、Blocking gates `PASS`、Warning count `0`。官方迁移漏斗保持 `690/1097（62.90%）`，说明质量治理没有改变编译覆盖口径。

首次启用远端门禁后，Linux runner 进一步暴露了外部工作簿探测的跨平台问题：硬编码 Windows 路径在 POSIX 上会被当成一个超长文件名，`Path.is_file()` 抛出 `ENAMETOOLONG`，导致 pytest 在收集阶段失败。测试现统一读取可选的 `FINDSL_OFFICIAL_WORKBOOK` 环境变量，并通过受控探测函数将 `OSError/ValueError` 判定为“外部资产不可用”；对应测试被正确 skip，其他异常仍照常暴露。该边界有专门单元测试，不通过全局异常吞噬解决。
