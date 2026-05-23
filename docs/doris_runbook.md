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

The script defaults `DORIS_EVIDENCE_MIN_SPEEDUP` to `10.0`, matching the competition acceleration target. Keep this default for final submission evidence; lower values are useful only for connectivity smoke tests and will not close the readiness performance warning.

The readiness gate treats Doris-scale evidence as valid only when all of these markers are present:

- both baseline and optimized SQL execute successfully,
- baseline and optimized row counts match,
- measured Doris speedup meets the 10x target,
- the baseline plan contains a window path,
- the optimized plan contains a prefix table path.

For password-protected private clusters, set `DORIS_PASSWORD` and `DORIS_PASSWORD_MODE=inline`. Inline passwords are redacted in the generated report's command template. Use shell history controls appropriate for your environment before recording final evidence.

## Production Notes

- Increase `replication_num` and bucket counts for multi-BE clusters.
- Keep the generated monthly `trade_date` auto partitions unless the production retention policy requires day or year granularity.
- Keep base and prefix tables in the same colocate group when their bucket count, replica layout, and distribution column type match.
- Rebuild prefix tables after base-table loads, or replace them with Doris materialized views when validated.
- Re-run `scripts/collect_doris_evidence.ps1` whenever data volume, table layout, or optimizer rules change.

Official references:

- [Apache Doris CREATE TABLE](https://doris.apache.org/docs/4.x/sql-manual/sql-statements/table-and-view/table/CREATE-TABLE/)
- [Apache Doris Auto Partitioning](https://doris.apache.org/docs/4.x/table-design/data-partitioning/auto-partitioning/)
- [Apache Doris Stream Load](https://doris.apache.org/docs/4.x/key-features/stream-load/)
- [Apache Doris Window Functions](https://doris.apache.org/docs/dev/query-data/window-function/)
