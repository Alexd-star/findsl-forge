# 运行测试与 Doris

## 1. 本地安装

建议 Python 3.11、Java 21、Docker Desktop 和 WSL2。MySQL 客户端只用于连接 Doris 的 MySQL 协议端口，不需要安装 MySQL Server。

```powershell
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
```

可选依赖按用途安装：`.[service]` 用于 API，`.[external-data]` 用于离线同步公开数据。

## 2. 编译流程

```powershell
python -m findsl.cli official-slot-parse `
  "indicator('', '', '涨幅', '今日', '', '', '') > 5%" `
  --mode strict --frontend antlr --json

python -m findsl.cli official-slot-ir `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" --json

python -m findsl.cli official-slot-backend `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" --json

python -m findsl.cli official-explain `
  "indicator('', '', '成交量', '近5000日', '', 'SUM', '') > 10000000"

python -m findsl.cli official-result `
  "indicator('', '', '成交量', '今日', '', '', '') > 100" `
  --output output/findsl-result.md
```

正常输出应包含阶段状态、Typed/Logical/Physical 信息、Doris SQL 和结构校验结果。错误输入应返回稳定错误码、源位置和说明，不应输出可执行假 SQL。

## 3. Web 与 API

```powershell
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
```

访问 `http://127.0.0.1:8765`。API 容器资产位于 `deploy/api/`；本地密钥和 `service.env` 不进入 Git。

API 启动后可在不执行 Doris 的情况下协商单条 DSL 能力。本地开发模式可使用：

```powershell
$env:FINDSL_ENV = "development"
python -m findsl.cli serve-api --host 127.0.0.1 --port 8766

$body = @{ dsl = "indicator('', '', '成交量', '今日', '', '', '') > 100" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/v1/capabilities/query `
  -ContentType "application/json" -Body $body
```

返回状态为 `SUPPORTED`、`DATA_UNAVAILABLE`、`INVALID_INPUT` 或 `CAPABILITY_GAP`。它与正式编译共用上下文和计划，不是宽松兼容入口。

一键启动 Doris、样例数据和容器化 Demo：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_stack.ps1
```

如 Docker 构建访问 PyPI 需要本机代理，使用 `-ProxyUrl http://127.0.0.1:7897`。脚本会将回环地址转换为容器可访问的 `host.docker.internal`，不会把代理固化进镜像运行环境。

脚本在保留 Doris 命名卷的前提下完成健康等待、样例装载、Demo 构建与 `/health` 核验。只查看状态使用 `-Action Status`，停止使用 `-Action Stop`。

## 4. 代码质量门禁

```powershell
python scripts/generate_antlr.py --check
python -m ruff check .
lint-imports
python -m pytest
python -m findsl.cli official-suite --json
```

- ANTLR check 证明生成代码和唯一文法源一致。
- Ruff 证明静态代码规则通过。
- import-linter 证明正式编译器没有反向依赖旧管道。
- Pytest 证明已有断言未回归，不单独证明业务正确率。
- official-suite 证明固定正例和负例行为稳定，不单独证明真实 Doris 语义。

金融规则候选发布使用：

```powershell
python scripts/validate_financial_rule_release.py `
  --baseline configs/official/financial_rules.json `
  --candidate path/to/candidate-financial-rules.json `
  --output reports/financial-rule-release-validation.json
```

候选校验通过不等于自动生效；只有状态、审批标识和生效区间满足要求的 `active` 发布才能进入正式编译上下文。

## 5. 启动 Doris

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\doris_quickstart.ps1 -Action Start
```

脚本使用命名卷保存 FE 元数据和 BE 数据。健康状态必须同时满足 FE HTTP、BE HTTP、查询端口可用且 backend alive。停止服务使用 `-Action Stop`；除非明确需要重建，不要删除命名卷。

用 MySQL 客户端核验：

```powershell
mysql -h 127.0.0.1 -P 9030 -u root -e "SHOW FRONTENDS; SHOW BACKENDS;"
```

## 6. 官方数据装载与水位

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_official_doris_evidence.ps1
python scripts\check_official_watermarks.py
```

装载必须满足 strict mode、`NumberFilteredRows=0`、基础表行数一致、日期范围一致和特征表可用。已有完整数据时脚本复用现有表，不应每次清空重载。

## 7. 正确率与性能

```powershell
python scripts\run_official_correctness_benchmark.py
python scripts\run_official_full_performance_matrix.py
python scripts\run_official_compile_latency_benchmark.py --repeats 30
python scripts\run_official_long_horizon_matrix.py --repeats 5
python scripts\generate_capability_matrix.py
python scripts\generate_blind_extension_evidence.py `
  --json-output reports\blind_extension_evidence.json `
  --report-output reports\blind_extension_evidence.md
python scripts\run_hero_query.py --execute-doris --timeout 30
```

执行前先通过水位门禁。正确率比较完整结果集；性能矩阵至少包含一次预热和多次重复，并保存结果哈希、P95 和 Git HEAD。任何失败都应先判断是代码、数据水位、连接、缓存还是资源问题，不要直接改阈值。

## 8. Readiness 与证据导出

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

导出脚本只复制当前白名单证据，并重建 `evidence_manifest.md`、`evidence_metadata.json` 和 `evidence_summary.md`。若合同失败，不得手工把状态改成 PASS；应修复 Git 身份、数据指纹或缺失报告后重跑。

## 9. 常见问题

| 现象 | 检查 |
| --- | --- |
| `lint-imports` 找不到 | 检查用户 Python Scripts 是否在 PATH，或使用其绝对路径 |
| 9030 无法连接 | 检查 Docker Desktop、WSL2、FE/BE 容器和端口占用 |
| backend 不 alive | 查看 BE 日志、磁盘空间和 FE 注册状态 |
| 水位不一致 | 核对 CSV 哈希、装载标签、过滤行数、表行数和日期范围 |
| SQL 能执行但结果不对 | 比较 Logical/Physical IR、reference SQL、排序和完整结果哈希 |
| 性能波动 | 固定缓存策略、并发、预热、重复次数和 Docker 资源，再比较 P95 |
