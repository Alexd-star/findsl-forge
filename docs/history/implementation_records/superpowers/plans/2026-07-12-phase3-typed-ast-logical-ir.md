# Phase 3 Typed AST and Logical IR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the official syntax AST, produce a strongly typed immutable tree, and lower supported official queries into validated Calcite-style logical plans without changing existing SQL output.

**Architecture:** Keep `official_slot.py` as a compatibility facade while moving syntax types into `official.ast`. Add one semantic result model, one immutable logical IR, and a strict lowering boundary; run the new pipeline in shadow mode and preserve the existing compiler as the user-visible backend.

**Tech Stack:** Python frozen dataclasses, structural visitors, deterministic JSON/SHA-256, pytest, pandas official-workbook audit, existing ANTLR/handwritten frontends.

---

### Task 1: Extract syntax AST with identity-compatible re-exports

**Files:**
- Create: `src/findsl/official/ast.py`
- Modify: `src/findsl/official_slot.py`
- Modify: `src/findsl/official/frontend/ast_adapter.py`
- Test: `tests/official/ir/test_ast_compatibility.py`

- [ ] Write tests asserting old and new imports are identical classes, all node JSON remains unchanged, traversal order is deterministic, and frozen nodes reject mutation.
- [ ] Run `python -m pytest tests/official/ir/test_ast_compatibility.py -v`; expect import failure for `findsl.official.ast`.
- [ ] Move the eight AST classes into `official.ast`, add `iter_child_nodes()` and `walk()`, then re-export the same class objects from `official_slot.py`.
- [ ] Run the focused test plus `tests/test_official_slot.py`; expect all tests to pass.
- [ ] Commit with `refactor: extract official syntax AST`.

### Task 2: Introduce explicit official types and compatibility rules

**Files:**
- Create: `src/findsl/official/types.py`
- Test: `tests/official/ir/test_types.py`

- [ ] Write tests for singleton names, range types, arithmetic/logical/ordered/equality/approximate compatibility, stable serialization, and rejection of incompatible operands.
- [ ] Run the focused test; expect import failure.
- [ ] Implement `TypeKind`, frozen `OfficialType`, `RangeType`, singleton values, and pure compatibility functions returning types or raising `OfficialTypeError`.
- [ ] Run the focused test; expect all tests to pass.
- [ ] Commit with `feat: add official compiler type system`.

### Task 3: Produce immutable Typed AST from semantic analysis

**Files:**
- Create: `src/findsl/official/typed_ast.py`
- Modify: `src/findsl/official/semantics.py`
- Test: `tests/official/ir/test_typed_ast.py`
- Test: `tests/test_official_semantics.py`

- [ ] Write tests for typed literals, arithmetic, boolean predicates, range children, all 12 function bindings, unknown indicators, deterministic serialization, and `validate()` compatibility.
- [ ] Run focused tests; expect missing `analyze()`/TypedNode failures.
- [ ] Implement frozen `FunctionBinding` and `TypedNode`; refactor semantic inference so `analyze()` builds children and binding once and `validate()` returns `legacy_name`.
- [ ] Run focused semantic suites; expect no existing error-code regression.
- [ ] Commit with `feat: build typed official AST`.

### Task 4: Define deterministic logical expression and relational IR

**Files:**
- Create: `src/findsl/official/ir/__init__.py`
- Create: `src/findsl/official/ir/base.py`
- Create: `src/findsl/official/ir/expressions.py`
- Create: `src/findsl/official/ir/relational.py`
- Test: `tests/official/ir/test_logical_ir.py`

- [ ] Write construction tests for every expression and relational node, schema uniqueness, immutable tuples, deterministic `to_dict()`, and content-derived node IDs.
- [ ] Run focused tests; expect import failure.
- [ ] Implement frozen nodes, `Field`, `Schema`, canonical JSON, and SHA-256-derived `node_id` without SQL text or random UUIDs.
- [ ] Run focused tests; expect all tests to pass.
- [ ] Commit with `feat: define deterministic logical IR`.

### Task 5: Validate logical plan invariants

**Files:**
- Create: `src/findsl/official/ir/validate.py`
- Test: `tests/official/ir/test_ir_validation.py`

- [ ] Write failing tests for non-boolean filters, negative/zero limits, invalid rank direction/bounds, duplicate schema fields, unknown strict types, physical table names, and valid nested plans.
- [ ] Run focused tests; expect missing validator failure.
- [ ] Implement `OfficialIrError(code, message, path)` and recursive validation with stable paths and cycle protection.
- [ ] Run focused tests; expect all tests to pass.
- [ ] Commit with `feat: validate official logical plans`.

### Task 6: Lower supported Typed AST into Logical IR

**Files:**
- Create: `src/findsl/official/lowering.py`
- Test: `tests/official/ir/test_lowering.py`

- [ ] Write golden tests for boolean filter, arithmetic comparison, between, limit, rank comparison, chained then stages, unsupported unknown types, and repeated-plan hash equality.
- [ ] Run focused tests; expect missing lowering API.
- [ ] Implement expression lowering, logical scan/filter/limit/rank/stage construction, required-function tracking, and `UNSUPPORTED_LOGICAL_LOWERING` diagnostics.
- [ ] Validate every successful plan before returning it.
- [ ] Run focused tests and semantic tests; expect all tests to pass.
- [ ] Commit with `feat: lower typed official AST to logical IR`.

### Task 7: Add CLI and official-workbook IR evidence

**Files:**
- Create: `src/findsl/official_ir_evidence.py`
- Modify: `src/findsl/cli.py`
- Test: `tests/test_official_ir_evidence.py`

- [ ] Write tests for single-query `official-slot-ir` JSON and 5,799-row evidence aggregation with input hash, typed/lowered/validated counts, error classes, node distribution, function coverage, deterministic plan hashes, and P50/P95.
- [ ] Run focused tests; expect missing commands/modules.
- [ ] Implement bounded-memory aggregation and explicit evidence gate: no validator failure among successful plans, no Phase 2 parse regression, and no strict compile regression.
- [ ] Run official evidence to `reports/phase3_official_ir_evidence.json/md` and inspect every blocking category.
- [ ] Commit code/tests with `feat: add official logical IR evidence`.

### Task 8: Document, verify, archive, and push

**Files:**
- Create: `docs/38_Typed_AST与Logical_IR实现说明.md`
- Modify: `README.md`
- Modify: `.github/workflows/test.yml`
- Create: `reports/phase3_official_ir_evidence.json`
- Create: `reports/phase3_official_ir_evidence.md`

- [ ] Document architecture, commands, supported/unsupported lowering, evidence boundaries, rollback, and next-stage optimizer boundary in natural Chinese.
- [ ] Run `python scripts/generate_antlr.py --check`, `python -m pytest -q`, `git diff --check`, and verify a clean worktree.
- [ ] Regenerate evidence against the final implementation commit and force-add ignored reports.
- [ ] Push through `127.0.0.1:7897`, then verify local and remote branch HEAD are identical.
- [ ] Preserve the worktree and feature branch for Phase 4.
