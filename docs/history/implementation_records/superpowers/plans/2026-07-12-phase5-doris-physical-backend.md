# Phase 5 Doris Physical Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select auditable Doris physical resources for grounded domain plans, render SQL exclusively through SQLGlot ASTs, and prove syntax, safety, determinism, and eligible result equivalence without replacing the legacy backend.

**Architecture:** A schema-validated physical catalog feeds a bounded candidate planner. Selected Physical IR is validated, converted to SQLGlot expressions, round-tripped in Doris dialect, compared structurally with the legacy backend, and optionally executed through the existing Doris evidence connection.

**Tech Stack:** Python frozen dataclasses, SQLGlot pinned Doris dialect, JSON catalogs, pytest, MySQL protocol Doris executor, canonical SHA-256 evidence.

---

### Task 1: Pin SQLGlot and prove Doris dialect behavior
- Modify `pyproject.toml`; create `tests/official/backend/test_sqlglot_runtime.py`.
- RED on missing SQLGlot, then pin one exact version and test SELECT/CTE/window/rank/literal round trips.
- Commit `build: pin SQLGlot Doris backend runtime`.

### Task 2: Physical catalog and migration
- Create `configs/official/physical_catalog.json`, schema, `official/physical/catalog.py`, and migration script.
- Test identifiers, logical/physical type parity, missing-domain exclusion, resource capabilities, prefix protocol and cache determinism.
- Generate mappings for official basic/ext/technical/prefix resources without embedding SQL fragments.
- Commit `feat: add official Doris physical catalog`.

### Task 3: Physical IR and validator
- Create `official/physical/ir.py`, `validate.py`, and exports.
- Test all scan/filter/join/aggregate/window/rank/limit/prefix/empty nodes, schema invariants, resource/column resolution and forbidden logical/missing inputs.
- Commit `feat: define validated Doris physical IR`.

### Task 4: Candidate enumeration and bounded cost model
- Create `official/physical/planner.py` and tests.
- Test direct, technical, prefix and unavailable candidates; explicit reject reasons; deterministic cost ordering; missing-statistics estimated flag; decision trace.
- Commit `feat: select auditable Doris physical candidates`.

### Task 5: SQLGlot Doris AST backend
- Create `official/backend/doris.py`, `validation.py`, exports, and tests.
- Cover direct indicator predicates, arithmetic/boolean/between, market/date constraints, rank outer filtering and limit.
- Require SQLGlot literals/identifiers, Doris render/parse/render stability, allowed resources, stable keys and old safety lint.
- Commit `feat: render Doris SQL from physical IR`.

### Task 6: Legacy/new structural and execution diff
- Create `official/backend/diff.py`, `executor.py`, and tests.
- Normalize AST aliases/formatting, compare resources/operators/contracts, and define deterministic result hashing for unordered and ordered contracts.
- Reuse MySQL-protocol Doris settings without logging credentials.
- Commit `feat: compare shadow Doris backend results`.

### Task 7: CLI and official backend evidence
- Create `official_backend_evidence.py`; modify `cli.py`; add tests.
- Add `official-slot-physical`, `official-slot-backend`, and `official-backend-evidence` commands.
- Audit all 5,799 rows, protect Phase 1–4 floors, record exact failure domains, SQLGlot/safety pass counts, structural diffs, P50/P95 and optional real Doris result hashes.
- Commit `feat: add official Doris backend evidence`.

### Task 8: Documentation, full verification, evidence archive, and push
- Create `docs/40_Doris物理规划与SQL_AST后端说明.md`; update README.
- Run generated-source check, all tests, official backend evidence, whitespace/clean-status audits.
- Bind reports to final implementation commit, push through `127.0.0.1:7897`, verify local/remote HEAD, preserve worktree for Phase 6.
