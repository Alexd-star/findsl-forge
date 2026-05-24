# Architecture

## Current MVP

```text
findsl.cli
  -> NL2DSL candidate layer
    -> template/rule match over official-style Chinese requests
    -> candidate DSL list with confidence and rationale
  -> Safe LLM candidate adapter
    -> parse structured/markdown model responses into DSL candidates
    -> reject direct SQL-looking output before compilation
    -> validate surviving candidates through compiler + equivalence verifier
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
    -> DorisSqlValidator
      -> enforce single SELECT/WITH query shape
      -> reject forbidden statement tokens, unknown tables, and window-in-WHERE SQL
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
  -> OfficialSuite
    -> run official-style positive cases across filters/rank/windows/prefix sums
    -> run negative DSL cases through stable diagnostics and repair suggestions
  -> DorisAssetGenerator
    -> emit partitioned/colocated DDL, sample inserts, prefix build SQL, smoke queries
  -> DorisEvidenceCollector
    -> compile baseline-window and optimized-prefix SQL
    -> capture Doris EXPLAIN, COUNT(*) latency, row-count parity, and 10x speedup marker
  -> RealMarketSample
    -> version cached Eastmoney quote JSON and CSV fixtures for business-demo validation
  -> Demo/API and ReadinessReport
    -> validate natural-language candidates through compiler + equivalence verifier
    -> validate optional LLM DSL candidates without allowing SQL bypass
    -> expose baseline, official-positive, and diagnostic-negative presets
    -> return structured diagnostics and repair hints for invalid requests
    -> generate defense walkthrough and score-mapping evidence
    -> consume official-style coverage suite as a required submission gate
    -> consume Doris cluster evidence markers for submission gating
```

## Design Decisions

### Deterministic Core

The compiler core is deterministic. AI support stays outside the core as an NL2DSL candidate or repair assistant. This avoids schema hallucination, unstable SQL output, and weak reproducibility.

### NL2DSL Candidate Layer

Natural-language requests are translated into candidate DSL, not directly into SQL. A candidate is useful only after it compiles, executes against local SQL fixtures, and matches the Pandas reference evaluator. This makes the AI-facing path defensible in competition review: convenience comes from natural-language entry, while correctness still comes from the same compiler and oracle used by the deterministic DSL path.

The template layer intentionally covers official-style edge cases that are easy for free-form text-to-SQL to mishandle: low-value ranking uses `rank(..., asc, bottom=N)`, high-value ranking uses `rank(..., desc, top=N)`, percentage ranking uses `percent=N`, signed net-outflow thresholds stay negative, return-rate prompts map to `RET(close, N)` instead of an ad hoc price subtraction, and date-range moving-average requests preserve window history through safe upper-bound pruning instead of treating the MA window as a numeric threshold.

### Safe LLM Candidate Adapter

The optional LLM adapter treats model output as untrusted proposal text. It extracts candidate DSL from JSON payloads, markdown fences, labeled lines, or OpenAI-style `choices[].message.content`, then applies a hard safety boundary:

```text
LLM response -> candidate extractor -> SQL bypass rejection -> compiler -> SQL/reference equivalence
```

Direct SQL-looking output is rejected with `UNSAFE_DIRECT_SQL`. Invalid DSL still enters the normal diagnostic layer, so misspelled indicators produce the same stable repair evidence as hand-written DSL. Accepted candidates are therefore useful only when they survive parser, semantic validation, SQL generation, optimizer explain, and the independent reference oracle. The deterministic Chinese templates include A/B market constraints, rank cutoffs, rolling windows, moving-average thresholds, signed money-flow thresholds, and date-range prefix-sum requests so live demo prompts do not depend on free-form SQL generation.

### Diagnostics Layer

Compiler, API, and demo failures are converted into structured diagnostics with stable codes and repair hints. This keeps interactive use productive during demonstrations: invalid indicators, parse errors, lexical issues, and semantic type mistakes point users back to supported indicators, functions, and DSL patterns instead of exposing only a traceback.

The Web Demo also exposes official negative presets from the same JSONL corpus used by the readiness gate. Selecting a negative preset runs the normal analyzer path, shows the expected diagnostic code beside the actual diagnostic code, and renders repair suggestions from the shared diagnostics layer. This makes error handling demonstrable instead of only testable.

String literals are escaped inside the compiler before they are emitted into Doris SQL. This keeps the deterministic DSL path from becoming a SQL-fragment bypass when a user supplies a market value or other string literal containing quotes.

After SQL generation, a Doris SQL validator checks the query shape before the compile result is accepted. It requires a single `SELECT` or `WITH` query, rejects DDL/DML tokens and statement separators outside string literals, checks known table references against the registry, and catches window functions emitted directly inside `WHERE`. Successful validation is recorded as `DORIS_SQL_VALIDATION` in structured explain.

### Typed AST Before SQL

DSL is parsed into AST nodes before SQL is generated. This supports:

- validation before execution,
- traceable rewrites,
- future logical IR,
- snapshot tests,
- better error messages.

### Feature Materialization

All generated stock-screening relations are anchored on `daily_quote`, even when the DSL only references auxiliary indicators such as `main_net_inflow`. Auxiliary tables are `LEFT JOIN`ed on `(ts_code, trade_date)` so the compiler keeps the same stock-date universe as the Pandas oracle and does not silently drop rows with missing optional data.

Financial screening expressions often contain rolling windows. SQL engines generally do not allow window functions directly in `WHERE`, and nested window functions are unsafe. The generator therefore builds feature layers:

```text
base relation
  -> numeric window features, such as MA/MAX
  -> LAG-based return-rate features, such as RET
  -> rolling boolean features, such as CONS/EXIST
  -> outer WHERE filter
```

This is intentionally closer to production SQL than string-template demos.

### Date-Range Pushdown

`date_between("YYYY-MM-DD", "YYYY-MM-DD")` compiles into a direct `trade_date` range predicate and emits a `DATE_RANGE_PUSHDOWN` explain step. When the filter does not depend on rolling windows, the generator also copies the full range into the physical base scan and emits `DATE_RANGE_BASE_PRUNING`, making Doris partition pruning visible in SQL. Window-dependent filters keep the lower bound outside the feature layer so rolling history is not truncated, but still push the safe upper bound into the base scan and emit `DATE_RANGE_WINDOW_PRUNING` because current-row and preceding-row windows never need future rows. Prefix-sum eligible `SUM(indicator(...), N)` filters are a special case: the current rows can use full date-range pruning while previous prefix values are fetched by `row_no`, so the optimizer emits `DATE_RANGE_PREFIX_PRUNING`.

### Config-Driven Business Rules

Indicators, tables, and functions live in `configs/`. The compiler should not need code changes when adding common indicators.

The defense package includes a config-only extension check that injects a temporary `alpha_score` indicator into a copied registry and compiles it through the normal compiler and Doris SQL validator. This turns the "new indicator without compiler-core changes" claim into executable evidence instead of a document-only assertion.

### Prefix-Sum Optimizer

Rolling `SUM` can be expensive for long financial windows. When an indicator declares `supports_prefix_sum`, `prefix_table`, and `prefix_column`, the generator rewrites:

```text
SUM(indicator(x), N)
```

into joins against the configured prefix table. The generated expression subtracts the prefix value at `row_no - N` from the current prefix value, producing the same rolling sum with a lookup-style plan that can be backed by Doris aggregate models, materialized views, or sorted duplicate-key tables.

For auxiliary indicators, prefix tables are built on the `daily_quote` trading-calendar skeleton and left-join the auxiliary source values before computing `row_no` and cumulative sums. This prevents sparse auxiliary tables from shifting rolling-window boundaries or losing quote rows on dates where the auxiliary value is absent.

Rank cutoffs apply a null-expression guard before `ROW_NUMBER()` so sparse auxiliary indicators do not select stocks whose ranking value is missing. Percent cutoffs still compute the partition count over the full stock-date relation, matching the reference oracle.

### Structured Explain

The compiler emits two explanation layers:

```text
trace: human-readable rewrite log
explain: machine-readable rule/status/evidence records
```

`explain` records applied and skipped rules, such as `PREFIX_SUM`, `WINDOW_FEATURE`, `RETURN_RATE`, `ROLLING_BOOLEAN`, `FEATURE_LAYER`, `FILTER_OUTER_WHERE`, and `DORIS_SQL_VALIDATION`. This makes optimizer behavior auditable and gives downstream reports or UI components stable fields to render.

## Next Enterprise Extensions

- Logical IR node model.
- SQLGlot optional validation.
- Broader Doris execution equivalence beyond the current evidence path.
- Broader prefix-sum optimizer coverage for more aggregate shapes.
- Materialized-view routing.
- More provider-backed LLM repair loops.
- Larger real-market data ingestion, including real money-flow feeds.

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

Both SQL variants must match the reference output and each other. The report includes local timing plus plan-shape signals such as window frame count and prefix table references. This separates lightweight regression timing from the Doris-scale performance claim, which is supported by the dedicated cluster evidence file.

## Official-Style Coverage Loop

The official-style suite is a compact regression corpus designed around the competition task shape:

```text
positive DSL case -> compiler -> SQL/trace/explain evidence -> SQL/reference equivalence
negative DSL case -> compiler failure -> structured diagnostic code -> repair suggestions
```

Positive cases cover staged filters, staged filter-to-filter pipelines, rank-then-filter relation preservation, repeated rank recomputation without stale `rank_no` collisions, top-N and percent-cutoff ranking with deterministic `ts_code` tie-breaking, derived-feature ranking, date-range pushdown, prefix-sum full-range pruning, window-safe date pruning, return-rate screening, market predicates, sparse auxiliary-table `LEFT JOIN` preservation, daily-quote anchoring for auxiliary-only filters, rolling boolean functions, moving averages, rolling extrema including `MIN`, prefix-sum aggregates over quote and money-flow tables, arithmetic predicates, signed numeric thresholds, SQL-standard equality normalization, mixed-case function names, case-insensitive indicator lookup, and case-insensitive market-code normalization. Negative cases cover unknown indicators, unknown functions, semantic type errors, invalid windows, non-integer windows, invalid return-rate nesting, invalid rank percentages, invalid rank directions, non-integer or non-positive rank cutoffs, invalid date ranges, invalid market arguments, literal/static division by zero, malformed numeric literals, bare column-name bypass attempts, invalid `filter` conditions, invalid `then` stages, top-level type mistakes, parse errors, lexical errors, unsupported rank parameters, duplicate named arguments, and invalid named-argument ordering. The readiness report treats this suite as a required gate so competition-style coverage cannot regress silently.

## Defense Package Loop

The defense package converts engineering evidence into a live-demonstration sequence:

```text
demo scenario -> executable check -> scoring point -> expected visible signal -> Markdown report
```

It covers NL2DSL validation, safe LLM candidate validation, prefix-sum official positive presets, diagnostic negative presets, Doris SQL validation, config-only indicator extension, official-style corpus coverage, compiler accuracy/latency, Doris deployment asset integrity, and the latest Doris cluster proof when `reports/doris_cluster_evidence.md` is present.

## Doris Evidence Loop

The Doris evidence collector uses the same compiler modes on a real Apache Doris query port:

```text
DSL -> compiler(prefix off) -> baseline window SQL -> Doris EXPLAIN + COUNT(*)
DSL -> compiler(prefix on)  -> prefix-sum SQL       -> Doris EXPLAIN + COUNT(*)
```

The generated `reports/doris_cluster_evidence.md` records connection metadata with passwords redacted, the DSL, both SQL variants, EXPLAIN text, repeated query latency, row-count parity, plan-shape markers, and the minimum speedup target. Readiness closes the `Doris-scale performance proof` warning only when baseline and optimized variants both execute, row counts match, the measured Doris speedup reaches the default 10x target, the baseline path contains a window plan, and the optimized path contains the prefix table.

## Real-Market Sample Loop

The versioned sample under `data/real_samples/eastmoney_a_share_sample/` keeps public Eastmoney raw JSON together with normalized CSV files and metadata:

```text
Eastmoney raw K-line JSON -> normalized CSV fixtures -> verify-sql -> SQL/reference parity
```

This path is intentionally small. It proves that the same DSL compiler and reference oracle can run against real stock codes, dates, closes, turnover rates, and volume fields, while the 5M Doris dataset remains the performance evidence source. The placeholder money-flow CSV is documented as neutral compatibility data and is not used as real money-flow proof.

## Doris Deployment Assets

The Doris asset generator converts configuration into executable SQL files:

```text
configs/*.json + data/samples/*.csv
  -> 01_schema.sql
  -> 02_sample_data.sql
  -> 03_build_prefix_tables.sql
  -> 04_smoke_queries.sql
```

This keeps table names, indicator columns, prefix columns, and smoke queries aligned with the compiler registry. The generated schema also gives the optimizer story a physical counterpart: all base and prefix tables use monthly `trade_date` auto partitions for pruning and a shared `ts_code` colocate group for local prefix joins. Production deployment should still tune replication, buckets, partition retention, and materialized-view strategy per cluster.
