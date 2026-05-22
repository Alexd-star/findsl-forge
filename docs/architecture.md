# Architecture

## Current MVP

```text
findsl.cli
  -> NL2DSL candidate layer
    -> template/rule match over official-style Chinese requests
    -> candidate DSL list with confidence and rationale
  -> Compiler
    -> Parser
      -> Lexer
      -> AST
    -> SemanticAnalyzer
      -> Registry(configs/*.json)
    -> SqlGenerator
      -> Feature materialization layers
      -> Prefix-sum feature rewrite when configured
      -> SQL text
      -> rewrite trace
      -> structured optimizer explain
  -> SQLiteSampleExecutor
    -> load CSV fixtures as physical tables
    -> execute generated SQL locally
  -> PandasReferenceEvaluator
    -> direct DSL interpretation over CSV sample tables
    -> semantic oracle result set
  -> EquivalenceVerifier
    -> compare SQL result keys with reference result keys
  -> PrefixSumBenchmark
    -> compile baseline window SQL and optimized prefix SQL
    -> compare correctness, timing, and plan shape
  -> DorisAssetGenerator
    -> emit DDL, sample inserts, prefix build SQL, smoke queries
  -> DorisEvidenceCollector
    -> compile baseline-window and optimized-prefix SQL
    -> capture Doris EXPLAIN, COUNT(*) latency, row-count parity, and 10x speedup marker
  -> Demo/API and ReadinessReport
    -> validate natural-language candidates through compiler + equivalence verifier
    -> return structured diagnostics and repair hints for invalid requests
    -> consume Doris cluster evidence markers for submission gating
```

## Design Decisions

### Deterministic Core

The compiler core is deterministic. AI support stays outside the core as an NL2DSL candidate or repair assistant. This avoids schema hallucination, unstable SQL output, and weak reproducibility.

### NL2DSL Candidate Layer

Natural-language requests are translated into candidate DSL, not directly into SQL. A candidate is useful only after it compiles, executes against local SQL fixtures, and matches the Pandas reference evaluator. This makes the AI-facing path defensible in competition review: convenience comes from natural-language entry, while correctness still comes from the same compiler and oracle used by the deterministic DSL path.

### Diagnostics Layer

Compiler, API, and demo failures are converted into structured diagnostics with stable codes and repair hints. This keeps interactive use productive during demonstrations: invalid indicators, parse errors, lexical issues, and semantic type mistakes point users back to supported indicators, functions, and DSL patterns instead of exposing only a traceback.

### Typed AST Before SQL

DSL is parsed into AST nodes before SQL is generated. This supports:

- validation before execution,
- traceable rewrites,
- future logical IR,
- snapshot tests,
- better error messages.

### Feature Materialization

Financial screening expressions often contain rolling windows. SQL engines generally do not allow window functions directly in `WHERE`, and nested window functions are unsafe. The generator therefore builds feature layers:

```text
base relation
  -> numeric window features, such as MA/MAX
  -> rolling boolean features, such as CONS/EXIST
  -> outer WHERE filter
```

This is intentionally closer to production SQL than string-template demos.

### Config-Driven Business Rules

Indicators, tables, and functions live in `configs/`. The compiler should not need code changes when adding common indicators.

### Prefix-Sum Optimizer

Rolling `SUM` can be expensive for long financial windows. When an indicator declares `supports_prefix_sum`, `prefix_table`, and `prefix_column`, the generator rewrites:

```text
SUM(indicator(x), N)
```

into joins against the configured prefix table. The generated expression subtracts the prefix value at `row_no - N` from the current prefix value, producing the same rolling sum with a lookup-style plan that can be backed by Doris aggregate models, materialized views, or sorted duplicate-key tables.

### Structured Explain

The compiler emits two explanation layers:

```text
trace: human-readable rewrite log
explain: machine-readable rule/status/evidence records
```

`explain` records applied and skipped rules, such as `PREFIX_SUM`, `WINDOW_FEATURE`, `ROLLING_BOOLEAN`, `FEATURE_LAYER`, and `FILTER_OUTER_WHERE`. This makes optimizer behavior auditable and gives downstream reports or UI components stable fields to render.

## Planned Enterprise Extensions

- Logical IR node model.
- Doris dialect validator.
- SQLGlot optional validation.
- Doris execution equivalence against Pandas reference results.
- Broader prefix-sum optimizer coverage for more aggregate shapes.
- Materialized-view routing.
- Benchmark report generator.
- API and UI.

## Correctness Loop

The project uses two independent execution paths for the same DSL:

```text
DSL -> compiler -> SQL -> SQLiteSampleExecutor -> result keys
DSL -> PandasReferenceEvaluator -> result keys
```

The equivalence layer compares `(ts_code, trade_date)` keys and reports missing or extra rows. This makes correctness measurable before large-scale Doris deployment, and it gives the final submission a reproducible semantic proof instead of only screenshots or hand-picked examples.

## Benchmark Loop

The prefix-sum benchmark deliberately compares two compiler modes for the same DSL:

```text
DSL -> compiler(prefix off) -> baseline window SQL -> SQLite fixture
DSL -> compiler(prefix on)  -> prefix-sum SQL       -> SQLite fixture
DSL -> PandasReferenceEvaluator -> semantic oracle
```

Both SQL variants must match the reference output and each other. The report includes local timing plus plan-shape signals such as window frame count and prefix table references. This separates correctness evidence from later Doris-scale performance claims.

## Doris Evidence Loop

The Doris evidence collector uses the same compiler modes on a real Apache Doris query port:

```text
DSL -> compiler(prefix off) -> baseline window SQL -> Doris EXPLAIN + COUNT(*)
DSL -> compiler(prefix on)  -> prefix-sum SQL       -> Doris EXPLAIN + COUNT(*)
```

The generated `reports/doris_cluster_evidence.md` records connection metadata with passwords redacted, the DSL, both SQL variants, EXPLAIN text, repeated query latency, row-count parity, plan-shape markers, and the minimum speedup target. Readiness closes the `Doris-scale performance proof` warning only when baseline and optimized variants both execute, row counts match, the measured Doris speedup reaches the default 10x target, the baseline path contains a window plan, and the optimized path contains the prefix table.

## Doris Deployment Assets

The Doris asset generator converts configuration into executable SQL files:

```text
configs/*.json + data/samples/*.csv
  -> 01_schema.sql
  -> 02_sample_data.sql
  -> 03_build_prefix_tables.sql
  -> 04_smoke_queries.sql
```

This keeps table names, indicator columns, prefix columns, and smoke queries aligned with the compiler registry. The generated SQL is a smoke-test path; production deployment should tune replication, buckets, partitioning, and materialized-view strategy per cluster.
