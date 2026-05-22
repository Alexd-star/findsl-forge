# Architecture

## Current MVP

```text
findsl.cli
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
```

## Design Decisions

### Deterministic Core

The compiler core is deterministic. LLM support will be placed outside the core as an NL2DSL or repair assistant. This avoids schema hallucination, unstable SQL output, and weak reproducibility.

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
