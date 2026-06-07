# 14 常见问题 FAQ

## 1. 为什么不直接让大模型生成 SQL？

金融筛选 SQL 涉及窗口、排名、日期边界、多表 join 和 NULL 语义。直接让大模型生成 SQL 容易出现不可审计、不可复现、口径不一致的问题。FinDSL Forge 让大模型只生成 DSL 候选，最终仍由确定性编译器和 reference oracle 验证。

## 2. 运行时提示找不到 `findsl` 怎么办？

在仓库根目录设置：

```powershell
$env:PYTHONPATH="src"
```

然后重新运行命令。

## 3. 为什么本地用 SQLite 验证 Doris SQL？

SQLite 用于快速本地语义回归，不代表最终性能环境。项目会注册少量 Doris 兼容函数，例如 `CEIL`，让本地执行器能执行生成 SQL。最终性能结论仍以 Doris evidence 为准。

## 4. `reports/` 为什么不提交？

`reports/` 是本地生成产物，可能包含大量渲染 QA、浏览器缓存和临时证据。最终提交使用 `submission_artifacts/evidence_snapshots/` 中的轻量快照。

## 5. 真实行情样本能证明性能吗？

不能。真实行情小样本用于业务可信展示；性能证明使用 Doris 规模数据、EXPLAIN、行数一致和 latency evidence。

## 6. Doris 连接失败怎么办？

检查 Docker Desktop、Doris 容器、9030 端口和 MySQL 客户端。可先运行：

```powershell
mysql --user=root --port=9030 --host=127.0.0.1 -e "SELECT 1"
```

## 7. 修改配置后需要做什么？

运行相关测试，并视情况重新生成 Doris 资产：

```powershell
python -m pytest tests\test_config_extension.py tests\test_compiler.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
```

## 8. readiness 出现 warning 怎么办？

查看 `reports/submission_readiness.md` 的 Gate Matrix。常见 warning 是 Git 工作区不干净、缺少 Doris 证据或 scale benchmark 证据。根据 warning 类型提交、还原或重新生成证据。

