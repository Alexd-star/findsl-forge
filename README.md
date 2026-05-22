# FinDSL Forge

FinDSL Forge is an enterprise-grade prototype for the 2026 Graduate FinTech Innovation Competition topic:

> Topic 19: Compile stock-screening DSL into high-performance Apache Doris SQL.

The project goal is not to let an LLM freely hallucinate SQL. The core path is deterministic:

```text
DSL -> Lexer/Parser -> Typed AST -> Semantic Validation -> SQL Plan -> Doris SQL
```

LLM/NL2DSL can be added as an assistant layer later, while the compiler remains auditable, reproducible, and testable.

## Current MVP Scope

- Parse nested stock-screening DSL expressions.
- Validate indicators, functions, named parameters, and window arguments from configuration.
- Compile `filter`, `then`, `rank`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, and `MIN` into SQL.
- Generate trace metadata explaining the selected rewrite path.
- Execute generated SQL against local SQLite fixtures for regression checks.
- Compare SQL output with an independent Pandas semantic reference evaluator.
- Rewrite eligible rolling `SUM` expressions to prefix-sum table joins for long-window acceleration.
- Run without non-standard Python dependencies.
- Provide pytest coverage for parser, semantic validation, SQL generation, and SQL/reference equivalence.

## Quick Start

```powershell
python -m pytest
python -m findsl.cli compile 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))'
python -m findsl.cli evaluate --input data/samples/queries.jsonl --output reports/evaluation_report.md
python -m findsl.cli reference 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json
```

If running from the repository root without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reference_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify_sql_sample.ps1
```

## Semantic Reference Evaluation

The repository includes a small sample A-share-style dataset under `data/samples/`.
`PandasReferenceEvaluator` interprets DSL directly over those CSV tables. It is intentionally independent from the SQL generator, so it can serve as a slow but trustworthy semantic oracle.

This is the foundation for later SQL equivalence tests:

```text
DSL -> Pandas reference result
DSL -> compiler -> SQLite/Doris SQL result
compare result sets
```

The current implementation already runs the generated SQL over in-memory SQLite tables loaded from CSV fixtures. SQLite is used as a lightweight local execution harness, while the generated SQL remains Doris-oriented and window-safe. This gives every compiler change a fast semantic regression gate before the Doris execution path is introduced.

## Prefix-Sum Optimization

Indicators can declare prefix-sum support in `configs/indicators.json`. When the compiler sees an eligible `SUM(indicator(...), window)` expression, it rewrites the rolling window aggregate into prefix table joins:

```text
window_sum = current_prefix - prefix_at_row_no_minus_window
```

This is the first optimizer path aimed at the competition's long-range query acceleration requirement. Unsupported indicators still use ordinary SQL window functions, so the optimization is safe and configuration-driven.

## Competition-Oriented Design

This repository is built around the topic's quantitative requirements:

- SQL correctness target: `>= 95%`
- Compile P95 target: `< 50ms`
- Long-range acceleration target: `10x+`
- New indicator/function target: core compiler code change `0 lines`

The first commit establishes a reliable compiler kernel. Later phases will add Doris execution, prefix-sum routing, benchmark reports, a web demo, and NL2DSL repair loops.
