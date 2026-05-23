# 现场演示脚本

## 演示前检查

```powershell
git status --short --branch
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1
```

如果需要重跑 Doris 5M 证据：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_doris_scale_evidence.ps1 -ProxyUrl "http://127.0.0.1:7897"
```

## 5 分钟主线

1. 打开 Web Demo，说明系统主链路：自然语言 -> DSL -> AST -> Doris SQL -> reference verification。
2. 默认中文需求：`筛选A股连续3天主力净流入为正的股票，并按换手率从高到低排名前100`。
3. 展示候选 DSL 通过验证，SQL/reference 行数一致。
4. 切到 SQL 标签页，指出 CTE、窗口、rank 排序和稳定 tie-breaker。
5. 选择 `Official positive: 主力净流入3日滚动求和走资金流前缀表`，展示 prefix table SQL。
6. 选择 `Diagnostic negative: 未知指标名`，展示 `UNKNOWN_INDICATOR` 和 `indicator("close")` 修复建议。
7. 展示 `submission_artifacts/evidence_snapshots/doris_cluster_evidence.md`，强调 5M 行真实 Doris 证据、结果一致、加速超过 10x。
8. 展示 `submission_artifacts/evidence_snapshots/submission_readiness.md`，强调 blocking gates 全通过、warning 为 0。
9. 展示 Git 状态和 bundle 备份，说明可回溯。

## 兜底路线

如果现场 Doris 容器不可用，不现场重跑 5M 数据，改为展示已导出的证据快照和本地 readiness。Doris 证据文件中包含 SQL、EXPLAIN、行数一致性、baseline/optimized 延迟和 speedup，可离线审阅。

如果 Web Demo 端口被占用：

```powershell
python -m findsl.cli serve-demo --port 8766
```

如果自然语言模板没有匹配，直接选择官方正例下拉项。评审重点是确定性编译、验证和 Doris 证据，不依赖大模型现场稳定性。
