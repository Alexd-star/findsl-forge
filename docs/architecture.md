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
      -> SQL text
      -> rewrite trace
  -> SQLiteSampleExecutor
    -> load CSV fixtures as physical tables
    -> execute generated SQL locally
  -> PandasReferenceEvaluator
    -> direct DSL interpretation over CSV sample tables
    -> semantic oracle result set
  -> EquivalenceVerifier
    -> compare SQL result keys with reference result keys
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

## Planned Enterprise Extensions

- Logical IR node model.
- Doris dialect validator.
- SQLGlot optional validation.
- Doris execution equivalence against Pandas reference results.
- Prefix-sum optimizer.
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
