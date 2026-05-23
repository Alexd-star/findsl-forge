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

The template layer intentionally covers official-style edge cases that are easy for free-form text-to-SQL to mishandle: low-value ranking uses `rank(..., asc, bottom=N)`, high-value ranking uses `rank(..., desc, top=N)`, percentage ranking uses `percent=N`, signed net-outflow thresholds stay negative, and date-range moving-average requests preserve window history through safe upper-bound pruning instead of treating the MA window as a numeric threshold.

### Safe LLM Candidate Adapter

The optional LLM adapter treats model output as untrusted proposal text. It extracts candidate DSL from JSON payloads, markdown fences, labeled lines, or OpenAI-style `choices[].message.content`, then applies a hard safety boundary:

```text
LLM response -> candidate extractor -> SQL bypass rejection -> compiler -> SQL/reference equivalence
```

Direct SQL-looking output is rejected with `UNSAFE_DIRECT_SQL`. Invalid DSL still enters the normal diagnostic layer, so misspelled indicators produce the same stable repair evidence as hand-written DSL. Accepted candidates are therefore useful only when they survive parser, semantic validation, SQL generation, optimizer explain, and the independent reference oracle.

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

Financial screening expressions often contain rolling windows. SQL engines generally do not allow window functions directly in `WHERE`, and nested window functions are unsafe. The generator therefore builds feature layers:

```text
base relation
  -> numeric window features, such as MA/MAX
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

### Structured Explain

The compiler emits two explanation layers:

```text
trace: human-readable rewrite log
explain: machine-readable rule/status/evidence records
```

`explain` records applied and skipped rules, such as `PREFIX_SUM`, `WINDOW_FEATURE`, `ROLLING_BOOLEAN`, `FEATURE_LAYER`, `FILTER_OUTER_WHERE`, and `DORIS_SQL_VALIDATION`. This makes optimizer behavior auditable and gives downstream reports or UI components stable fields to render.

## Planned Enterprise Extensions

- Logical IR node model.
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

## Official-Style Coverage Loop

The official-style suite is a compact regression corpus designed around the competition task shape:

```text
positive DSL case -> compiler -> SQL/trace/explain evidence -> SQL/reference equivalence
negative DSL case -> compiler failure -> structured diagnostic code -> repair suggestions
```

Positive cases cover staged filters, staged filter-to-filter pipelines, top-N and percent-cutoff ranking, derived-feature ranking, date-range pushdown, prefix-sum full-range pruning, window-safe date pruning, market predicates, rolling boolean functions, moving averages, rolling extrema including `MIN`, prefix-sum aggregates over quote and money-flow tables, arithmetic predicates, signed numeric thresholds, SQL-standard equality normalization, and mixed-case function names. Negative cases cover unknown indicators, unknown functions, semantic type errors, invalid windows, non-integer windows, invalid rank percentages, invalid rank directions, non-integer or non-positive rank cutoffs, invalid date ranges, invalid market arguments, literal/static division by zero, malformed numeric literals, bare column-name bypass attempts, invalid `filter` conditions, invalid `then` stages, top-level type mistakes, parse errors, lexical errors, unsupported rank parameters, and invalid named-argument ordering. The readiness report treats this suite as a required gate so competition-style coverage cannot regress silently.

## Defense Package Loop

The defense package converts engineering evidence into a live-demonstration sequence:

```text
demo scenario -> executable check -> scoring point -> expected visible signal -> Markdown report
```

It covers NL2DSL validation, safe LLM candidate validation, prefix-sum official positive presets, diagnostic negative presets, Doris SQL validation, config-only indicator extension, official-style corpus coverage, compiler accuracy/latency, and Doris deployment asset integrity. It deliberately does not claim real Doris 10x performance; that remains gated by the Doris evidence collector and a real cluster report.

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

This keeps table names, indicator columns, prefix columns, and smoke queries aligned with the compiler registry. The generated schema also gives the optimizer story a physical counterpart: all base and prefix tables use monthly `trade_date` auto partitions for pruning and a shared `ts_code` colocate group for local prefix joins. Production deployment should still tune replication, buckets, partition retention, and materialized-view strategy per cluster.
