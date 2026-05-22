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
- Doris dialect SQL compatibility tests.
- EXPLAIN capture and analysis.

Metrics:

- SQL execution success.
- Result latency.
- Query plan characteristics.

## Phase 4: Adaptive Optimizer

Status: started.

Deliverables:

- Query feature extraction.
- Long-range query detection.
- Prefix-sum rewrite path. (Started for eligible rolling `SUM`)
- Baseline-vs-optimized benchmark report. (Started for local SQLite fixtures)
- Materialized-view route path.
- Partition and column pruning hints.
- Plan explanation JSON.

Metrics:

- Long-range acceleration target: 10x+ versus baseline full-scan SQL.
- Compile P95 target: < 50ms.
- Execution target: <= 10s for official-scale tests.
- Optimized SQL and baseline SQL must match the independent reference result before performance claims are accepted.

## Phase 5: Enterprise Demo and Submission Package

Deliverables:

- Web UI or Streamlit UI.
- AST/IR/SQL/rewrite trace visualization.
- Markdown table output for official sample questions.
- One-minute demo video.
- Lean canvas.
- Technical document.
- Deployment and test manual.

## Non-Negotiable Quality Gates

- All tests pass before commit.
- No hard-coded business indicators in compiler core.
- Every non-trivial rewrite emits trace text.
- New indicators should require config-only changes.
- SQL generation must avoid nested window functions and window expressions directly in `WHERE`.
