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

## Production Notes

- Increase `replication_num` and bucket counts for multi-BE clusters.
- Partition large production tables by `trade_date`.
- Rebuild prefix tables after base-table loads, or replace them with Doris materialized views when validated.
- Capture `EXPLAIN` plans for baseline and optimized SQL before making performance claims.

Official references:

- [Apache Doris CREATE TABLE](https://doris.apache.org/docs/4.x/sql-manual/sql-statements/table-and-view/table/CREATE-TABLE/)
- [Apache Doris Stream Load](https://doris.apache.org/docs/4.x/key-features/stream-load/)
- [Apache Doris Window Functions](https://doris.apache.org/docs/dev/query-data/window-function/)
