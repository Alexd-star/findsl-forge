# FinDSL Forge

FinDSL Forge is an enterprise-grade prototype for the 2026 Graduate FinTech Innovation Competition topic:

> Topic 19: Compile stock-screening DSL into high-performance Apache Doris SQL.

The project goal is not to let an LLM freely hallucinate SQL. The core path is deterministic:

```text
DSL -> Lexer/Parser -> Typed AST -> Semantic Validation -> SQL Plan -> Doris SQL
```

AI/NL2DSL is implemented as an assistant layer that proposes DSL candidates. Every candidate still flows through the deterministic compiler and SQL/reference equivalence check, so the core remains auditable, reproducible, and testable.

## Current MVP Scope

- Parse nested stock-screening DSL expressions.
- Validate indicators, functions, named parameters, and window arguments from configuration.
- Compile `filter`, `then`, `rank`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, and `MIN` into SQL.
- Generate trace metadata explaining the selected rewrite path.
- Emit structured optimizer explain steps for machine-readable rewrite evidence.
- Return structured compile diagnostics and repair hints for invalid DSL/API requests.
- Execute generated SQL against local SQLite fixtures for regression checks.
- Compare SQL output with an independent Pandas semantic reference evaluator.
- Rewrite eligible rolling `SUM` expressions to prefix-sum table joins for long-window acceleration.
- Produce baseline-window versus prefix-sum benchmark reports.
- Generate deterministic synthetic A-share-style data for reproducible long-window scale benchmarks.
- Generate Doris DDL, sample load, prefix-table build, and smoke-query assets.
- Serve a local Web Demo/API for DSL, AST, Doris SQL, optimizer explain, and SQL/reference verification.
- Suggest DSL candidates from Chinese natural-language stock-screening requests, then validate them through the compiler and reference oracle.
- Generate a submission readiness report covering tests, accuracy, equivalence, optimizer evidence, Doris assets, and git rollback state.
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
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json
python -m findsl.cli suggest-dsl '筛选A股连续三天主力净流入为正并按换手率排名前一百' --data-dir data/samples --json
python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.md
python -m findsl.cli scale-benchmark --stocks 300 --days 260 --window 120 --iterations 5 --output reports/prefix_sum_scale_benchmark.md
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
python -m findsl.cli readiness-report --output reports/submission_readiness.md
```

If running from the repository root without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)'
python -m findsl.cli suggest-dsl '今日收盘价创二百五十日新高'
powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reference_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify_sql_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_prefix_sum.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\scale_benchmark.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
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

The `benchmark-prefix-sum` command compiles the same DSL twice: once with prefix-sum disabled as a baseline window query, and once with prefix-sum enabled. It then checks both SQL outputs against the Pandas reference result and writes a Markdown report with timing and plan-shape evidence. Local SQLite timings are treated as regression signals; Doris-scale acceleration must be proven later with Doris data and `EXPLAIN`.

`scripts/scale_benchmark.ps1` goes one step further: it generates deterministic synthetic market data under `data/generated/scale/`, runs a 120-day rolling `SUM` query against baseline-window and prefix-sum SQL, and writes `reports/prefix_sum_scale_benchmark.md`. The report records correctness gates, local timing, plan shape, and a long-window feature-access reduction estimate. It is designed as reproducible pre-Doris evidence, not as a substitute for Doris cluster `EXPLAIN` and production latency.

## Structured Explain

Compiler JSON output includes both human-readable `trace` text and machine-readable `explain` steps. Each explain step records a rule name, status, message, and evidence dictionary. This lets evaluation reports, future UI panels, and answer-defense materials show why an optimization was applied or skipped.

## Web Demo

`scripts/serve_demo.ps1` starts a local Web Demo at `http://127.0.0.1:8765`. The demo lets judges or teammates enter an official-style Chinese stock-screening request, review compiler-validated DSL candidates, choose a sample DSL, run the deterministic compiler, inspect Doris SQL, AST, optimizer explain, and SQL/reference verification rows, and receive repair hints when invalid DSL is submitted.

The same server exposes JSON APIs:

- `GET /api/examples`
- `POST /api/suggest`
- `POST /api/analyze`

## Doris Assets

`scripts/generate_doris_assets.ps1` creates the SQL files under `deploy/doris/`:

```text
01_schema.sql
02_sample_data.sql
03_build_prefix_tables.sql
04_smoke_queries.sql
```

These files are a smoke-test deployment path for Doris. See `docs/doris_runbook.md` for execution order and production notes.

## Submission Readiness

`scripts/submission_readiness.ps1` generates `reports/submission_readiness.md` and companion evidence reports. The readiness report is designed as a pre-submission gate: it runs pytest, compiler evaluation, SQL/reference equivalence, prefix-sum benchmark checks, Demo API smoke checks, NL2DSL validated-candidate checks, structured diagnostics checks, Doris asset integrity checks, and git rollback-state inspection.

Required gates fail the command when correctness or asset integrity breaks. Warning gates highlight remaining competition risks, especially Doris-cluster scale proof and uncommitted local changes.

## Competition-Oriented Design

This repository is built around the topic's quantitative requirements:

- SQL correctness target: `>= 95%`
- Compile P95 target: `< 50ms`
- Long-range acceleration target: `10x+`
- New indicator/function target: core compiler code change `0 lines`

The first commits establish a reliable compiler kernel, correctness oracle, optimizer evidence, Doris assets, NL2DSL candidate validation, and a local demo. Later phases will add Doris-cluster execution proof, broader DSL coverage, and LLM-backed NL2DSL repair loops.
