# 真实行情数据接入与展示方案

当前 5M Doris 性能证据使用确定性合成数据，优势是可复现、可回归、适合评审复核。为了增强业务可信度，项目已经补充一组可版本化的公开真实行情小样本：`data/real_samples/eastmoney_a_share_sample/`。该样本来自东方财富公开历史 K 线接口，覆盖贵州茅台 `600519.SH` 与平安银行 `000001.SZ` 在 2024-01-02 至 2024-01-12 的日线数据。

这组样本用于展示真实字段、真实股票代码和真实交易日期下的 DSL 语义验证；性能结论仍以 5,000,000 行 Doris 规模证据为准。两类数据各自承担不同角色，答辩时不要混在同一个性能口径里。

## 推荐数据字段

`daily_quote.csv`

```text
ts_code,trade_date,close,turnover_rate,volume
```

`money_flow.csv`

```text
ts_code,trade_date,main_net_inflow
```

`stock_universe.csv`

```text
ts_code,trade_date,market
```

## 接入原则

- 保持列名与 `configs/indicators.json` 一致。
- `trade_date` 使用 `YYYY-MM-DD`。
- `ts_code` 与三张表保持同一编码体系。
- 如果资金流表稀疏，prefix 构建会以 daily quote 为骨架 left join，保证 row_no 对齐。
- 真实数据只作为可信业务样例；5M 合成数据仍作为可复现实验基准。
- 当前真实样本中的 `money_flow.csv` 是中性占位文件，所有 `main_net_inflow` 为 0，仅用于保持三表加载器兼容 quote-only DSL。它不能作为真实资金流证据使用。

## 已实现样本

```text
data/real_samples/eastmoney_a_share_sample/
  daily_quote.csv
  stock_universe.csv
  money_flow.csv
  queries.jsonl
  source_metadata.json
  raw/*.json
```

样本验证命令：

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample
```

刷新公开接口缓存：

```powershell
python .\scripts\fetch_real_market_sample.py --refresh --proxy "http://127.0.0.1:7897"
```

## Doris 导入流程

如果需要把真实样本也导入 Doris，可按同一套 schema 和 Stream Load 流程操作。

1. 启动 Doris：

```powershell
docker compose -f .\deploy\doris\docker-compose.quickstart.yaml up -d
```

2. 运行 schema：

```powershell
mysql -h 127.0.0.1 -P 9030 -u root < .\deploy\doris\01_schema.sql
```

3. 使用 Doris Stream Load 导入三张 CSV。
4. 运行 `deploy/doris/03_build_prefix_tables.sql` 重建前缀表。
5. 运行 `scripts/collect_doris_evidence.ps1` 或 Web Demo 做业务样例展示。

## 答辩口径

真实样例用于证明业务字段和查询语义可信；合成 5M 数据用于证明同一套编译器和 Doris 物理设计在可复现实验下达到性能目标。两者不要混在一个结论里，避免评审质疑数据来源。
