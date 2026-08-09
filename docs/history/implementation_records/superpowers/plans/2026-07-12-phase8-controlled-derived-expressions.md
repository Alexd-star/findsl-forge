# Phase 8 Controlled Derived Expressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy derived SQL strings with a typed, schema-validated physical expression registry and expand the SQLGlot backend over high-frequency official indicators.

**Architecture:** JSON declares only a closed expression algebra. A loader recursively validates types and lowers declarations into Physical IR. The planner resolves direct fields first and controlled expressions second; SQL generation remains exclusively SQLGlot AST based.

**Tech Stack:** Python 3.9, dataclasses, JSON Schema contract, SQLGlot 28.5.0, Apache Doris, pytest.

---

### Task 1: Typed Physical Expression Registry

**Files:**
- Create: `src/findsl/official/physical/expressions.py`
- Create: `configs/official/physical_expressions.schema.json`
- Create: `configs/official/physical_expressions.json`
- Create: `tests/official/physical/test_expressions.py`

- [ ] Write failing tests for scaled-column, safe-ratio, boolean conjunction and invalid-type declarations.
- [ ] Implement immutable expression declarations, recursive type validation, canonical fingerprint and cached default loader.
- [ ] Add the first 20 controlled strategies and validate duplicate/resource/operator/identifier failures.
- [ ] Run focused tests and commit `feat: add controlled physical expressions`.

### Task 2: Physical IR and SQLGlot Rendering

**Files:**
- Modify: `src/findsl/official/physical/ir.py`
- Modify: `src/findsl/official/physical/validate.py`
- Modify: `src/findsl/official/backend/doris.py`
- Modify: `tests/official/backend/test_doris_backend.py`

- [ ] Write failing tests for negate, coalesce and explicit safe division rendering.
- [ ] Add Physical IR nodes and validator recursion.
- [ ] Render each node with SQLGlot expression classes and assert Doris round-trip stability.
- [ ] Run focused tests and commit `feat: render controlled derived expressions`.

### Task 3: Planner and Pipeline Integration

**Files:**
- Modify: `src/findsl/official/physical/planner.py`
- Modify: `src/findsl/official/pipeline.py`
- Modify: `src/findsl/cli.py`
- Modify: `tests/official/physical/test_planner.py`
- Modify: `tests/official/test_pipeline.py`

- [ ] Write failing tests for latest price, return percentage, limit flags, market capitalization and main-outflow plans.
- [ ] Add direct-first/derived-second indicator resolution and collect every required physical column.
- [ ] Pass the default expression registry through pipeline and CLI paths.
- [ ] Verify absent/missing-domain indicators remain rejected.
- [ ] Run focused tests and commit `feat: plan controlled derived indicators`.

### Task 4: Coverage and Doris Evidence

**Files:**
- Create: `reports/phase8_derived_expression_funnel.json`
- Create: `reports/phase8_derived_expression_funnel.md`
- Modify: `README.md`

- [ ] Rerun the 5,799-row migration funnel and compare all stage counts against Phase 7.
- [ ] Select deterministic newly eligible rows and execute old/new SQL on the same Doris snapshot.
- [ ] Require 100% row-count and SHA-256 agreement for enabled strategies.
- [ ] Run full pytest, ANTLR generation check and `git diff --check`.
- [ ] Commit evidence, push through the configured proxy and verify remote HEAD.
