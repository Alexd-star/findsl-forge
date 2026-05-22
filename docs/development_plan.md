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
- Future Doris optimizer with prefix-sum and materialized-view routing.
- Automated correctness, latency, and performance reports.

## Phase 1: Compiler Kernel MVP

Status: started.

Deliverables:

- Standard-library DSL lexer/parser.
- AST model.
- Semantic validation against configuration.
- Config-driven indicators, functions, and tables.
- SQL generation for `filter`, `then`, `rank`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, and `MIN`.
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
- Doris dialect SQL compatibility tests.
- EXPLAIN capture and analysis.

Metrics:

- SQL execution success.
- Result latency.
- Query plan characteristics.
- Doris assets should be regenerated from the same registry used by the compiler.

## Phase 4: Adaptive Optimizer

Status: started.

Deliverables:

- Query feature extraction.
- Long-range query detection.
- Prefix-sum rewrite path. (Started for eligible rolling `SUM`)
- Baseline-vs-optimized benchmark report. (Started for local SQLite fixtures)
- Deterministic synthetic market data and long-window scale benchmark report. (Started)
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
- Every optimizer decision that affects SQL shape should expose a machine-readable explain step.

## Phase 5: Enterprise Demo and Submission Package

Status: started.

Deliverables:

- Web UI or Streamlit UI. (Started via zero-dependency local Web Demo/API)
- AST/IR/SQL/rewrite trace visualization. (Started)
- Natural-language-to-DSL candidate layer with compiler/reference validation. (Started)
- Structured compile diagnostics and repair hints for invalid demo/API requests. (Started)
- Markdown table output for official sample questions. (Started via submission readiness reports)
- Submission readiness report covering tests, compiler metrics, SQL equivalence, optimizer evidence, Doris assets, and git rollback state. (Started)
- Long-window scale benchmark evidence linked from the readiness report when generated. (Started)
- One-minute demo video.
- Lean canvas.
- Technical document.
- Deployment and test manual.

Exit criteria:

- `scripts/submission_readiness.ps1` completes without required-gate failures.
- `scripts/serve_demo.ps1` opens a local demo where DSL, AST, Doris SQL, optimizer explain, and verification rows are visible in one workflow.
- Demo API smoke check remains a required readiness gate.
- NL2DSL smoke check proves the default Chinese request produces a validated DSL candidate whose SQL matches the independent reference result.
- Diagnostics smoke check proves invalid DSL produces stable repair guidance rather than only a traceback.
- Generated reports can be attached to the technical document or used in defense.
- Warning gates are either closed or explicitly explained in the final submission.

## Non-Negotiable Quality Gates

- All tests pass before commit.
- No hard-coded business indicators in compiler core.
- Every non-trivial rewrite emits trace text.
- New indicators should require config-only changes.
- SQL generation must avoid nested window functions and window expressions directly in `WHERE`.
