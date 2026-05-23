# FinDSL Forge

FinDSL Forge is an enterprise-grade prototype for the 2026 Graduate FinTech Innovation Competition topic:

> Topic 19: Compile stock-screening DSL into high-performance Apache Doris SQL.

The project goal is not to let an LLM freely hallucinate SQL. The core path is deterministic:

```text
DSL -> Lexer/Parser -> Typed AST -> Semantic Validation -> SQL Plan -> Doris SQL
```

AI/NL2DSL is implemented as an assistant layer that proposes DSL candidates. Every candidate still flows through the deterministic compiler and SQL/reference equivalence check, so the core remains auditable, reproducible, and testable.

## Implemented Scope

- Parse nested stock-screening DSL expressions.
- Validate indicators, functions, named parameters, duplicate named arguments, and window arguments from configuration.
- Compile `filter`, `then`, `rank` with top/bottom/percent cutoffs, `date_between`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, and `MIN` into SQL.
- Generate trace metadata explaining the selected rewrite path.
- Emit structured optimizer explain steps for machine-readable rewrite evidence.
- Validate generated SQL against a Doris-safe single-query shape before returning it.
- Return structured compile diagnostics and repair hints for invalid DSL/API requests.
- Prove config-only indicator extension through defense-package evidence.
- Execute generated SQL against local SQLite fixtures for regression checks.
- Compare SQL output with an independent Pandas semantic reference evaluator.
- Push safe date ranges and window-safe date upper bounds into base table scans for partition-pruning-friendly Doris SQL.
- Support signed numeric thresholds for net-flow and other negative-valued financial indicators.
- Normalize mixed-case indicator names and market codes for official-style input robustness.
- Preserve sparse auxiliary-table rows by anchoring stock-date semantics on `daily_quote` and left-joining optional tables.
- Rewrite eligible rolling `SUM` expressions to prefix-sum table joins for long-window acceleration.
- Use configured hot-window prefix columns such as `volume_sum_120` to avoid query-time prefix self-joins on competition-scale Doris evidence paths.
- Build auxiliary prefix tables from the daily quote trading-calendar skeleton so sparse money-flow data cannot shift rolling windows.
- Produce baseline-window versus prefix-sum benchmark reports.
- Generate deterministic synthetic A-share-style data for reproducible long-window scale benchmarks.
- Generate Doris DDL with trade-date auto partitions, colocated stock-code distribution, sample load, prefix-table build, and smoke-query assets.
- Collect Doris-cluster `EXPLAIN` and latency evidence for baseline-window versus prefix-sum SQL.
- Serve a local Web Demo/API for DSL, AST, Doris SQL, optimizer explain, and SQL/reference verification.
- Suggest DSL candidates from Chinese natural-language stock-screening requests, then validate them through the compiler and reference oracle.
- Cover official-style NL2DSL prompts for low-price bottom picks, turnover percent cuts, B-market average-volume thresholds, high-turnover close ranking, date-window moving-average filters, rolling minimum thresholds, date-prefix-sum pruning, and signed net-outflow thresholds.
- Validate optional LLM-proposed DSL candidates while rejecting direct SQL and invalid DSL before execution.
- Run an official-style coverage suite with representative positive cases and negative diagnostic cases.
- Generate a defense package that maps live demo steps to competition scoring evidence.
- Generate a submission readiness report covering tests, accuracy, equivalence, optimizer evidence, Doris assets, and git rollback state.
- Run without non-standard Python dependencies.
- Provide pytest coverage for parser, semantic validation, SQL generation, and SQL/reference equivalence.

Current readiness passes required gates and the Doris-scale performance proof. The recorded Doris evidence uses 5,000,000 synthetic daily quote rows, disables Doris SQL cache during timing, and shows a 36.24x cluster speedup for a 120-day rolling-volume prefix path.

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
python -m findsl.cli suggest-dsl 'A股存在资金流入后按低价取每日2只' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股每日换手率前50%' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'B股近2日均量不低于80' --data-dir data/samples --json
python -m findsl.cli suggest-dsl '主力净流出低于-1.5' --data-dir data/samples --json
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --text '近3日成交量累计大于300' --data-dir data/samples --json
python -m findsl.cli official-suite --output reports/official_suite_report.md --json
python -m findsl.cli defense-package --output reports/defense_package.md --json
python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.md
python -m findsl.cli scale-benchmark --stocks 300 --days 260 --window 120 --iterations 5 --output reports/prefix_sum_scale_benchmark.md
python -m findsl.cli collect-doris-evidence --host 127.0.0.1 --port 9030 --user root --database findsl_demo --dsl 'filter(SUM(indicator("volume"), 120) > 1000000)' --output reports/doris_cluster_evidence.md
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
python -m findsl.cli readiness-report --output reports/submission_readiness.md
```

If running from the repository root without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)'
python -m findsl.cli suggest-dsl '今日收盘价创二百五十日新高'
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --json
python -m findsl.cli official-suite --json
python -m findsl.cli defense-package --json
powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reference_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify_sql_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\official_suite.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\validate_llm_candidates.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\defense_package.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_prefix_sum.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\scale_benchmark.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_doris_scale_evidence.ps1 -ProxyUrl "http://127.0.0.1:7897"
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
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

This is the optimizer path aimed at the competition's long-range query acceleration requirement. Unsupported indicators still use ordinary SQL window functions, so the optimization is safe and configuration-driven. For sparse auxiliary sources, generated prefix tables are built from the daily quote trading calendar with a left join back to the auxiliary values, preserving the same stock-date universe used by the reference oracle.

The `benchmark-prefix-sum` command compiles the same DSL twice: once with prefix-sum disabled as a baseline window query, and once with prefix-sum enabled. It then checks both SQL outputs against the Pandas reference result and writes a Markdown report with timing and plan-shape evidence. Local SQLite timings are treated as regression signals; Doris-scale acceleration must be proven later with Doris data and `EXPLAIN`.

`scripts/scale_benchmark.ps1` goes one step further: it generates deterministic synthetic market data under `data/generated/scale/`, runs a 120-day rolling `SUM` query against baseline-window and prefix-sum SQL, and writes `reports/prefix_sum_scale_benchmark.md`. The report records correctness gates, local timing, plan shape, and a long-window feature-access reduction estimate. It is designed as reproducible pre-Doris evidence, not as a substitute for Doris cluster `EXPLAIN` and production latency.

After the Doris schema, data, and prefix tables are loaded, `scripts/collect_doris_evidence.ps1` captures real-cluster `EXPLAIN`, repeated `COUNT(*)` latency, row-count equivalence, plan-shape markers, and the default 10x speedup target into `reports/doris_cluster_evidence.md` plus a JSON sidecar. The readiness report consumes this file and closes the `Doris-scale performance proof` warning only when baseline and optimized SQL both succeed, row counts match, the baseline contains a window plan, the optimized query uses a prefix table, and measured Doris speedup meets the 10x target.

For the repeatable local 5M-row path, `scripts/prepare_doris_scale_evidence.ps1` starts the Docker Doris cluster, generates deterministic CSV data, Stream Loads the base tables, rebuilds prefix tables, collects Doris evidence, and reruns readiness. Use `-ProxyUrl "http://127.0.0.1:7897"` when Docker image pulls need the local VPN proxy.

## Structured Explain

Compiler JSON output includes both human-readable `trace` text and machine-readable `explain` steps. Each explain step records a rule name, status, message, and evidence dictionary. This lets evaluation reports, future UI panels, and answer-defense materials show why an optimization was applied or skipped.

## Web Demo

`scripts/serve_demo.ps1` starts a local Web Demo at `http://127.0.0.1:8765`. The demo lets judges or teammates enter an official-style Chinese stock-screening request, review compiler-validated DSL candidates, choose baseline cases or official-style positive/negative presets, run the deterministic compiler, inspect Doris SQL, AST, optimizer explain, and SQL/reference verification rows, and receive repair hints when invalid DSL is submitted. Negative presets show the expected and actual diagnostic code, making error recovery a live demonstration instead of a hidden test report.

The same server exposes JSON APIs:

- `GET /api/examples`
- `POST /api/suggest`
- `POST /api/analyze`

## Safe LLM Candidate Adapter

`validate-llm-candidates` is an offline safety adapter for model-proposed DSL. It accepts a structured or markdown-style LLM response file, extracts candidate FinDSL expressions, rejects direct SQL-looking output, compiles remaining DSL through the deterministic compiler, and requires SQL/reference equivalence when verification is enabled.

The bundled `data/samples/llm_candidate_response.json` intentionally contains one valid DSL candidate, one misspelled indicator, and one unsafe direct SQL candidate. This gives the defense package concrete evidence that LLM assistance is useful but cannot bypass parser, semantic validation, diagnostics, optimizer explain, or reference-oracle checks.

## Doris Assets

`scripts/generate_doris_assets.ps1` creates the SQL files under `deploy/doris/`:

```text
01_schema.sql
02_sample_data.sql
03_build_prefix_tables.sql
04_smoke_queries.sql
```

These files are a smoke-test deployment path for Doris. The schema generator emits monthly `trade_date` auto partitions plus a shared `colocate_with` group on `ts_code`, so the date-range pushdown and prefix-table joins have visible physical-design support. See `docs/doris_runbook.md` for execution order and production notes.

To capture cluster evidence for the submission gate:

```powershell
$env:DORIS_HOST="127.0.0.1"
$env:DORIS_PORT="9030"
$env:DORIS_USER="root"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

The script defaults `DORIS_EVIDENCE_MIN_SPEEDUP` to `10.0`, matching the competition acceleration target. Keep the default for final submission evidence so `submission_readiness.ps1` can validate the 10x marker.

For password-protected private clusters, set `DORIS_PASSWORD` and `DORIS_PASSWORD_MODE=inline`, or use `DORIS_PASSWORD_MODE=prompt` in an interactive shell. The generated report redacts inline passwords from the command template.

## Submission Readiness

`scripts/submission_readiness.ps1` generates `reports/submission_readiness.md` and companion evidence reports. The readiness report is designed as a pre-submission gate: it runs pytest, compiler evaluation, SQL/reference equivalence, prefix-sum benchmark checks, Demo API smoke checks, NL2DSL validated-candidate checks, structured diagnostics checks, Doris SQL validation evidence, config-only indicator extension evidence, Doris asset integrity checks, Doris cluster evidence marker checks, and git rollback-state inspection.

The readiness report also runs `official-suite`, which currently covers 31 positive official-style cases and 33 negative diagnostic cases across staged filters, top-N ranking, percent-cutoff ranking, date-range pushdown, window-safe date pruning, rolling boolean conditions, moving averages, rolling extrema, prefix-sum aggregates, hot-window materialized columns, market joins, arithmetic predicates, signed numeric thresholds, sparse auxiliary joins, repeated rank stages, case-insensitive inputs, duplicate named arguments, invalid dates, invalid rank directions, invalid windows, and invalid-DSL repair diagnostics. Each positive case must compile, expose expected SQL/trace/explain evidence, and match the independent SQL/reference result. Each negative case must fail with a stable diagnostic code and actionable suggestions.

It also validates the safe LLM candidate loop and generates `reports/defense_package.md`, a live-defense walkthrough that maps NL2DSL validation, official NL2DSL template coverage, LLM guardrails, prefix-sum positive presets, diagnostic negative presets, official coverage, compiler latency, Doris asset integrity, and the exported Doris proof to concrete scoring evidence.

Required gates fail the command when correctness or asset integrity breaks. Warning gates highlight competition risks such as missing Doris-cluster scale proof or uncommitted local changes.

Because `reports/` is generated and ignored by Git, run `scripts/export_submission_artifacts.ps1` before the final commit. It copies lightweight evidence reports into `submission_artifacts/evidence_snapshots/` so the submitted repository contains a reviewable evidence snapshot without committing large CSV data.

## Competition-Oriented Design

This repository is built around the topic's quantitative requirements:

- SQL correctness target: `>= 95%`
- Compile P95 target: `< 50ms`
- Long-range acceleration target: `10x+`
- New indicator/function target: core compiler code change `0 lines`

The current implementation establishes a reliable compiler kernel, correctness oracle, optimizer evidence, Doris assets, real Doris-cluster execution proof, NL2DSL and safe LLM candidate validation, official-style coverage evidence, and a local demo. Final polishing can add a small real-market-data sample and optional provider-backed LLM repair loops while preserving the same deterministic validation contract.
