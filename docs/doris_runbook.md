# Doris Runbook

This runbook prepares the generated SQL compiler output for an Apache Doris environment.

## Generate Assets

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
```

The script writes:

- `deploy/doris/01_schema.sql`
- `deploy/doris/02_sample_data.sql`
- `deploy/doris/03_build_prefix_tables.sql`
- `deploy/doris/04_smoke_queries.sql`

## Execute In Doris

Run the SQL files in order with a MySQL-compatible Doris client:

```powershell
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/01_schema.sql
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/02_sample_data.sql
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/03_build_prefix_tables.sql
mysql -h <fe_host> -P <query_port> -u <user> -p < deploy/doris/04_smoke_queries.sql
```

For larger data, use Doris Stream Load for CSV files instead of `INSERT INTO ... VALUES`.
The generated sample inserts are intentionally small smoke-test fixtures.

The generated schema uses monthly `trade_date` auto partitions and a shared `colocate_with` group over the `ts_code` hash distribution. This is intentional physical evidence for two competition-critical paths: safe date-range predicates can prune partitions, and prefix-table joins can remain locally distributed when cluster colocate conditions are satisfied.

Prefix tables for auxiliary sources, such as `dwd_stock_money_flow_prefix`, are rebuilt from the `dwd_stock_daily_quote` stock-date skeleton with a left join back to the auxiliary source table. This keeps `row_no` aligned with the compiler's daily-quote-anchored screening universe even when optional auxiliary rows are sparse.

## Physical Layout Preflight

Before recording final evidence, capture these checks from the Doris client. They prove the generated assets were actually loaded with the intended partition and colocate design:

```sql
USE findsl_demo;

SHOW CREATE TABLE dwd_stock_daily_quote;
SHOW CREATE TABLE dwd_stock_daily_quote_prefix;
SHOW CREATE TABLE dwd_stock_money_flow;
SHOW CREATE TABLE dwd_stock_money_flow_prefix;

SHOW PARTITIONS FROM dwd_stock_daily_quote;
SHOW PARTITIONS FROM dwd_stock_daily_quote_prefix;

SHOW PROC '/colocation_group';
```

Evidence to keep:

- base and prefix tables both show `AUTO PARTITION BY RANGE (date_trunc(..., 'month'))`,
- base and prefix tables use the same `DISTRIBUTED BY HASH(ts_code)` bucket count,
- related base and prefix tables share `colocate_with = findsl_stock_by_ts`,
- partition output contains the loaded trade-date months,
- colocate status is stable before latency sampling.

## Collect Cluster Evidence

After schema, sample or scale data, and prefix tables are loaded, collect the real Doris evidence consumed by the submission readiness gate:

```powershell
$env:DORIS_HOST="<fe_host>"
$env:DORIS_PORT="9030"
$env:DORIS_USER="<user>"
$env:DORIS_DATABASE="findsl_demo"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

The script writes:

- `reports/doris_cluster_evidence.md`
- `reports/doris_cluster_evidence.json`

By default, the evidence query is:

```text
filter(SUM(indicator("volume"), 120) > 420000)
```

This query is intentional: with prefix-sum disabled it produces a baseline `ROWS BETWEEN` window plan, and with prefix-sum enabled it should route to `dwd_stock_daily_quote_prefix`. Override it with `DORIS_EVIDENCE_DSL` only when the replacement query still exercises a long rolling `SUM` over a prefix-enabled indicator.

For the current local 5,000,000-row evidence run, the final high-selectivity query is:

```powershell
$env:DORIS_EVIDENCE_DSL='filter(SUM(indicator("volume"), 120) > 1000000)'
$env:DORIS_EVIDENCE_ITERATIONS="5"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

The collector disables Doris SQL cache for each MySQL client session with `SET enable_sql_cache=false`, so repeated evidence runs measure execution rather than a cached query result.

The script defaults `DORIS_EVIDENCE_MIN_SPEEDUP` to `10.0`, matching the competition acceleration target. Keep this default for final submission evidence; lower values are useful only for connectivity smoke tests and will not close the readiness performance warning.

The readiness gate treats Doris-scale evidence as valid only when all of these markers are present:

- both baseline and optimized SQL execute successfully,
- baseline and optimized row counts match,
- measured Doris speedup meets the 10x target,
- the baseline plan contains a window path,
- the optimized plan contains a prefix table path.

## Manual Evidence Cross-Checks

The collector automates the final report, but these manual checks are useful for screenshots and root-cause debugging if the readiness warning does not close:

```sql
-- Baseline SQL should contain a window frame after compiling with prefix-sum disabled.
EXPLAIN <baseline_window_sql>;

-- Optimized SQL should reference a generated prefix table.
EXPLAIN <optimized_prefix_sql>;

-- Row counts must match before timing claims are meaningful.
SELECT COUNT(*) AS baseline_rows FROM (<baseline_window_sql>) baseline_q;
SELECT COUNT(*) AS optimized_rows FROM (<optimized_prefix_sql>) optimized_q;
```

When the two row counts differ, treat it as a correctness failure rather than a performance issue. Check prefix-table rebuild order, row-number continuity per `ts_code`, and whether the benchmark DSL uses an indicator whose configuration declares `supports_prefix_sum = true`.

For latency evidence, warm the cluster once, then run the collector with at least three measured iterations:

```powershell
$env:DORIS_EVIDENCE_ITERATIONS="5"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

Keep the generated Markdown and JSON sidecar together. The Markdown is for the technical document and defense, while the JSON is safer for later automated comparison if table layout or optimizer rules change.

For password-protected private clusters, set `DORIS_PASSWORD` and `DORIS_PASSWORD_MODE=inline`. Inline passwords are redacted in the generated report's command template. Use shell history controls appropriate for your environment before recording final evidence.

## Production Notes

- Increase `replication_num` and bucket counts for multi-BE clusters.
- Keep the generated monthly `trade_date` auto partitions unless the production retention policy requires day or year granularity.
- Keep base and prefix tables in the same colocate group when their bucket count, replica layout, and distribution column type match.
- Rebuild prefix tables after base-table loads, or replace them with Doris materialized views when validated.
- Keep configured hot-window columns such as `volume_sum_120` in prefix tables when the target workload repeatedly asks for the same long rolling window.
- Re-run `scripts/collect_doris_evidence.ps1` whenever data volume, table layout, or optimizer rules change.

Official references:

- [Apache Doris CREATE TABLE](https://doris.apache.org/docs/4.x/sql-manual/sql-statements/table-and-view/table/CREATE-TABLE/)
- [Apache Doris Auto Partitioning](https://doris.apache.org/docs/4.x/table-design/data-partitioning/auto-partitioning/)
- [Apache Doris Stream Load](https://doris.apache.org/docs/4.x/key-features/stream-load/)
- [Apache Doris Window Functions](https://doris.apache.org/docs/dev/query-data/window-function/)
