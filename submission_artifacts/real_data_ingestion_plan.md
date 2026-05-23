# 真实行情数据接入方案

当前 5M Doris 性能证据使用确定性合成数据，优势是可复现、可回归、适合评审复核。为了增强业务可信度，最终提交可以追加一组真实或公开样例行情数据。

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

## 导入流程

1. 把真实 CSV 放入一个独立目录，例如 `data/generated/real_market_sample/`。
2. 启动 Doris：

```powershell
docker compose -f .\deploy\doris\docker-compose.quickstart.yaml up -d
```

3. 运行 schema：

```powershell
mysql -h 127.0.0.1 -P 9030 -u root < .\deploy\doris\01_schema.sql
```

4. 使用 Doris Stream Load 导入三张 CSV。
5. 运行 `deploy/doris/03_build_prefix_tables.sql` 重建前缀表。
6. 运行 `scripts/collect_doris_evidence.ps1` 或 Web Demo 做业务样例展示。

## 答辩口径

真实样例用于证明业务字段和查询语义可信；合成 5M 数据用于证明同一套编译器和 Doris 物理设计在可复现实验下达到性能目标。两者不要混在一个结论里，避免评审质疑数据来源。
