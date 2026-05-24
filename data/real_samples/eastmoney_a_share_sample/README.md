# Eastmoney A 股真实行情小样本

本目录用于补足答辩中的真实业务样本。`daily_quote.csv` 和 `stock_universe.csv` 来自东方财富公开历史 K 线接口，覆盖贵州茅台 `600519.SH` 与平安银行 `000001.SZ` 在 2024-01-02 至 2024-01-12 的日线数据。

`money_flow.csv` 是中性占位文件，所有 `main_net_inflow` 为 0，仅用于保持项目既有三表加载器可运行 quote-only DSL。它不能作为真实资金流证据使用，资金流性能与正确性仍以项目已有 Doris evidence 和样例数据为准。

推荐演示命令：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample
```

重新生成：

```powershell
python scripts\fetch_real_market_sample.py
# 如果要重新联网刷新 raw JSON，再追加 --refresh；需要代理时加 --proxy "http://127.0.0.1:7897"
```
