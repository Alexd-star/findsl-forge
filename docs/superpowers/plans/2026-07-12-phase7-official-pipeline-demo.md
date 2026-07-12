# Phase 7 Official Pipeline and Demo Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the ANTLR-to-SQLGlot official compiler as one auditable service, connect it to a dedicated Demo API, and generate a deterministic migration coverage funnel.

**Architecture:** A new orchestration module composes existing frontend, semantic, lowering, optimizer, physical planner, and Doris renderer APIs without duplicating their logic. Demo integration uses a separate endpoint with no implicit legacy fallback. A coverage command profiles every official workbook row and records the exact terminal stage and code.

**Tech Stack:** Python 3.9, ANTLR4 4.13.2, SQLGlot 28.5.0, pytest, JSON/JSONL, existing HTTP server.

---

### Task 1: Unified Official Pipeline

**Files:**
- Create: `src/findsl/official/pipeline.py`
- Create: `tests/official/test_pipeline.py`

- [ ] Write a failing success-path test asserting AST, logical, physical, decisions, SQL, validation and elapsed time.
- [ ] Run `python -m pytest tests/official/test_pipeline.py -v` and confirm the import fails because the pipeline does not exist.
- [ ] Implement immutable result/options/error types and `compile_official` by composing existing modules.
- [ ] Add failing tests for syntax, unavailable data domain and unavailable physical plan errors.
- [ ] Normalize each failure into `OfficialPipelineError` without losing original codes or partial stage outputs.
- [ ] Run the focused tests and commit `feat: add unified official compiler pipeline`.

### Task 2: Official Demo API

**Files:**
- Modify: `src/findsl/demo.py`
- Modify: `tests/test_demo.py`

- [ ] Write failing tests for `analyze_official_dsl` and `/api/official/analyze` routing.
- [ ] Confirm the tests fail because the function and route do not exist.
- [ ] Add the official analysis adapter and HTTP route; preserve `/api/analyze` unchanged.
- [ ] Return pipeline failures through the existing structured error envelope with stage, code and partial evidence.
- [ ] Run Demo tests and commit `feat: expose official compiler demo API`.

### Task 3: Versioned Official Demo Cases

**Files:**
- Create: `data/samples/official_slot_demo.jsonl`
- Modify: `src/findsl/demo.py`
- Modify: `tests/test_demo.py`

- [ ] Write a failing parametrized test that executes each case and checks its declared success or error code.
- [ ] Add official syntax cases for basic, security, ext, rank, constraints, technical and missing-domain behavior.
- [ ] Add `GET /api/official/examples` and confirm the JSON preserves expectation metadata.
- [ ] Run focused tests and commit `feat: add auditable official demo cases`.

### Task 4: Migration Coverage Funnel

**Files:**
- Create: `src/findsl/official_coverage_funnel.py`
- Modify: `src/findsl/cli.py`
- Create: `tests/official/test_coverage_funnel.py`

- [ ] Write failing tests for deterministic stage counts, migration denominator and error aggregation.
- [ ] Implement workbook profiling using the same pipeline stages and legacy strict outcome as the existing audit.
- [ ] Add CLI `official-coverage-funnel --workbook --json-output --report-output`.
- [ ] Generate Markdown containing stage funnel, old-to-new migration rate, top error codes and next implementation priorities.
- [ ] Run focused tests and commit `feat: report official backend migration funnel`.

### Task 5: Evidence and Verification

**Files:**
- Create: `reports/phase7_official_pipeline_funnel.md`
- Create: `reports/phase7_official_pipeline_funnel.json`
- Modify: `README.md`

- [ ] Generate the Phase 7 report from the official workbook and bind it to Git HEAD and input SHA-256.
- [ ] Update README with explicit old/new Demo endpoints and no-fallback policy.
- [ ] Run `python scripts/generate_antlr.py --check`.
- [ ] Run focused official and Demo tests, then `python -m pytest -q`.
- [ ] Run `git diff --check` and confirm a clean status after commit.
- [ ] Commit `evidence: archive Phase 7 official pipeline funnel`, push through the configured proxy, and verify remote HEAD.
