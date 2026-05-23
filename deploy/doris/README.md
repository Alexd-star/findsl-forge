# Doris Smoke Deployment Assets

Generated from the FinDSL registry and sample CSV fixtures.

Run order:

```text
01_schema.sql
02_sample_data.sql
03_build_prefix_tables.sql
04_smoke_queries.sql
```

These SQL files are intended for smoke validation. For larger market data, load CSV files with Doris Stream Load and then run `03_build_prefix_tables.sql`.

The generated schema includes monthly `trade_date` auto partitions and a shared `ts_code` colocate group for base and prefix tables. Keep those physical-design signals when collecting final Doris EXPLAIN and latency evidence.

Before running the final evidence collector, verify the physical layout in Doris:

```sql
SHOW CREATE TABLE dwd_stock_daily_quote;
SHOW CREATE TABLE dwd_stock_daily_quote_prefix;
SHOW PARTITIONS FROM dwd_stock_daily_quote;
SHOW PROC '/colocation_group';
```

The final report should be collected with `scripts/collect_doris_evidence.ps1` only after prefix tables are rebuilt and baseline/optimized row counts match.

## Local Docker Desktop quickstart

On Windows with Docker Desktop, start the local Doris 4.1.0 smoke cluster from the repository root:

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7897"
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
docker compose -f .\deploy\doris\docker-compose.quickstart.yaml up -d
mysql --user=root --port=9030 --host=127.0.0.1 -e "SELECT * FROM backends()"
```

Stop it with:

```powershell
docker compose -f .\deploy\doris\docker-compose.quickstart.yaml down
```
