# Development Plan

This plan turns Topic 19 into a staged, auditable engineering delivery.

## Goal

Build a deterministic compiler and optimization platform for stock-screening DSL:

```text
DSL -> Typed AST -> Semantic Validation -> Feature Layers -> Doris SQL -> Evaluation Report
```

The national-award target is to satisfy every explicit task while adding high-competition differentiators:

- Deterministic compiler instead of LLM-only SQL generation.
- Traceable AST and SQL rewrite process.
- Structured optimizer explain for auditable rewrite decisions.
- Config-driven indicator and function extension.
- Window-safe SQL generation using feature materialization layers.
- Doris optimizer with prefix-sum rewrite, hot-window materialization, and future materialized-view routing.
- Automated correctness, latency, and performance reports.

## Phase 1: Compiler Kernel MVP

Status: started.

Deliverables:

- Standard-library DSL lexer/parser.
- AST model.
- Semantic validation against configuration.
- Config-driven indicators, functions, and tables.
- SQL generation for `filter`, `then`, `rank`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, `MIN`, and `RET`.
- Cross-sectional `rank(..., percent=N)` cutoff support for percentage-based daily screening.
- Signed numeric thresholds for negative-valued financial indicators such as net outflow.
- Date-range pushdown through `date_between(...)`, including window-safe upper-bound pruning and prefix-sum full-range pruning, for partition-pruning-friendly SQL.
- Rewrite trace.
- Pytest baseline.

Exit criteria:

- `python -m pytest` passes.
- CLI can compile sample DSL to SQL and trace JSON.
- Git commit and backup bundle exist.

## Phase 2: Correctness Evaluation

Status: started.

Deliverables:

- Golden DSL dataset with expected AST and behavior.
- Pandas reference evaluator for stock screening semantics. (Done for MVP functions)
- SQLite SQL execution harness for generated SQL. (Done for sample fixtures)
- SQL-result equivalence tests. (Done for representative MVP cases)
- Markdown evaluation report.

Metrics:

- Compile success rate.
- Semantic equivalence accuracy.
- Error classification quality.

Exit criteria:

- `python -m pytest` passes with SQL/reference equivalence cases.
- `scripts/verify_sql_sample.ps1` proves compiled SQL and reference semantics agree on sample fixtures.
- Mismatched rows are reported as missing/extra `(ts_code, trade_date)` keys.

## Phase 3: Doris Execution Path

Deliverables:

- Doris Docker deployment or remote Doris adapter.
- DDL and import scripts for simulated A-share data.
- Generated Doris SQL assets and runbook. (Started)
- Doris-cluster evidence collector for baseline-window versus prefix-sum `EXPLAIN`, latency, and row-count parity. (Started)
- Doris dialect SQL compatibility tests and compiler-side safe query-shape validation. (Started)
- EXPLAIN capture and analysis.

Metrics:

- SQL execution success.
- Result latency.
- Query plan characteristics.
- Doris assets should be regenerated from the same registry used by the compiler.
- Readiness should consume `reports/doris_cluster_evidence.md` and close the Doris-scale proof warning only when row counts match, Doris speedup reaches the default 10x target, and both plan-shape markers are present.

## Phase 4: Adaptive Optimizer

Status: started.

Deliverables:

- Query feature extraction.
- Long-range query detection.
- Prefix-sum rewrite path. (Started for eligible rolling `SUM`)
- Baseline-vs-optimized benchmark report. (Started for local SQLite fixtures)
- Deterministic synthetic market data and long-window scale benchmark report. (Started)
- Real Doris evidence path for long-window optimizer proof. (Started)
- Materialized-view route path.
- Partition and column pruning hints.
- Plan explanation JSON.
- Structured optimizer explain. (Started for compiler, evaluation, and benchmark reports)

Metrics:

- Long-range acceleration target: 10x+ versus baseline full-scan SQL.
- Compile P95 target: < 50ms.
- Execution target: <= 10s for official-scale tests.
- Optimized SQL and baseline SQL must match the independent reference result before performance claims are accepted.
- Local scale benchmark must record dataset size, long-window plan shape, correctness gates, and the boundary between SQLite regression evidence and Doris production proof.
- Doris cluster evidence must record baseline-window and optimized-prefix plan shape plus measured 10x speedup before any production acceleration claim is accepted.
- Every optimizer decision that affects SQL shape should expose a machine-readable explain step.
- Prefix-sum eligible date-range queries must push the full date range into the base scan while keeping correctness through prefix-table lookups.

## Phase 5: Enterprise Demo and Submission Package

Status: started.

Deliverables:

- Web UI or Streamlit UI. (Started via zero-dependency local Web Demo/API)
- AST/IR/SQL/rewrite trace visualization. (Started)
- Natural-language-to-DSL candidate layer with compiler/reference validation. (Started)
- Official-style NL2DSL templates for bottom-rank, percent-rank, high-turnover rank, date-window MA, signed net-outflow, rolling-min, return-rate, and date-prefix-sum requests. (Started)
- Optional LLM response adapter that validates model-proposed DSL and rejects direct SQL bypasses. (Started)
- Structured compile diagnostics and repair hints for invalid demo/API requests. (Started)
- Official positive and diagnostic negative presets in the Web Demo for live defense walkthroughs. (Started)
- Official-style positive and negative coverage suite with SQL/trace/explain/equivalence evidence. (Started)
- Defense package report mapping live demo steps to scoring evidence. (Started)
- Markdown table output for official sample questions. (Started via submission readiness reports)
- Submission readiness report covering tests, compiler metrics, SQL equivalence, optimizer evidence, Doris assets, and git rollback state. (Started)
- Long-window scale benchmark evidence linked from the readiness report when generated. (Started)
- Doris cluster evidence report linked from readiness when generated. (Started)
- Versioned Web Demo screenshots for the positive compile path and diagnostic negative path. (Started)
- One-minute demo video generated from versioned screenshots. (Implemented)
- Public real-market A-share quote sample with SQL/reference verification, readiness gate, and defense-package evidence. (Implemented)
- Lean canvas.
- Technical document.
- Deployment and test manual.

Exit criteria:

- `scripts/submission_readiness.ps1` completes without required-gate failures.
- `scripts/serve_demo.ps1` opens a local demo where DSL, AST, Doris SQL, optimizer explain, and verification rows are visible in one workflow.
- Demo examples include baseline cases, official-style positive cases, and diagnostic negative cases with expected/actual diagnostic codes.
- `submission_artifacts/demo_screenshots/` contains current positive-path and negative-diagnostic screenshots for report/PPT use.
- `scripts/build_defense_video.py` generates `submission_artifacts/defense_video/findsl_forge_one_minute_demo.mp4` from the committed screenshots.
- `scripts/defense_package.ps1` produces a repeatable walkthrough that maps visible demo signals to competition scoring points.
- Demo API smoke check remains a required readiness gate.
- NL2DSL smoke check proves the default Chinese request produces a validated DSL candidate whose SQL matches the independent reference result.
- Defense package must prove NL2DSL official-template coverage for low-price `bottom`, turnover `percent`, date-window MA, signed net-outflow, rolling-min, return-rate, and date-prefix-sum pruning scenarios.
- LLM safety smoke check proves model-proposed output accepts only verified DSL, rejects direct SQL, and classifies invalid DSL with stable diagnostics.
- Diagnostics smoke check proves invalid DSL produces stable repair guidance rather than only a traceback.
- Defense package proves a config-only indicator extension can compile and pass Doris SQL validation without changing compiler core.
- Defense package separately exposes semantic hardening diagnostics for hidden-evaluation style invalid DSL.
- Real-market quote sample gate must verify cached raw payloads, metadata, and quote-only DSL cases without using the small sample as performance proof.
- Official-style coverage suite remains a required readiness gate, with representative positive cases passing SQL/reference equivalence and representative negative cases producing stable diagnostic codes plus repair hints.
- Doris-scale warning is closed only after `scripts/collect_doris_evidence.ps1` captures successful baseline and optimized Doris execution with row-count parity, required plan-shape markers, and default 10x speedup target satisfaction.
- Local SQLite prefix timing is only a smoke/regression signal and must not be presented as Doris-scale acceleration proof.
- Generated reports can be attached to the technical document or used in defense.
- Defense package must attach the latest real Doris 10x+ proof as separate cluster evidence, not confuse it with local fixture timing.
- Real-market quote samples should strengthen business credibility, while 5M Doris evidence remains the only performance-claim source.
- Warning gates are either closed or explicitly explained in the final submission.

## Non-Negotiable Quality Gates

- All tests pass before commit.
- No hard-coded business indicators in compiler core.
- Bare column-name comparisons must be rejected; configured fields must enter through `indicator(...)`.
- Relation-building functions must enforce typed contracts in semantic analysis: `filter` takes boolean conditions and `then` stages produce relations.
- Window functions must reject non-integer or non-positive windows before SQL generation, and top-level DSL expressions must be relation or boolean filter conditions.
- Symbolic predicate helpers such as `market(...)` must reject non-symbol arguments before SQL generation.
- Numeric expressions must reject literal or statically-foldable division by zero before SQL generation.
- Function names and `rank` limit argument names should be case-insensitive for official-style input robustness.
- DSL equality operators (`=`/`==`/`!=`) must normalize to SQL-standard Doris-compatible comparison operators.
- Every non-trivial rewrite emits trace text.
- New indicators should require config-only changes.
- SQL generation must avoid nested window functions and window expressions directly in `WHERE`.
- Generated SQL must pass the Doris-safe query-shape validator before a compile result is accepted.
- Official-style positive/negative corpora must grow with every newly supported DSL construct so competition coverage stays evidence-backed.
- Rank semantics must keep top/bottom/percent validation aligned across compiler SQL, Pandas reference, diagnostics, and official-suite cases; `top` is paired with `desc`, while `bottom` is paired with `asc` to avoid ambiguous low/high picks.
- NL2DSL rank templates must emit the same top/bottom/percent semantics as the compiler accepts, so AI-assisted entry cannot generate candidates that fail deterministic semantic validation.
- Date predicates must validate ISO dates, reject reversed ranges, expose `DATE_RANGE_PUSHDOWN`, and push safe non-window ranges into the base scan as `DATE_RANGE_BASE_PRUNING`.
- LLM/provider integrations may propose DSL only; they must never execute direct SQL or bypass compiler, diagnostics, optimizer explain, and equivalence checks.
