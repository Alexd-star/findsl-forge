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
