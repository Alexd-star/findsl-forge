# Phase 4 Domain IR, Registry, and Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind official function slots into validated financial-domain IR, migrate grounded indicator metadata into a schema-validated declarative registry, and optimize logical plans with deterministic auditable rules.

**Architecture:** A cached registry resolves names and aliases into logical indicator definitions. A domain binder converts Typed AST calls into SQL-free domain expressions and requirements; a deterministic rule engine rewrites only validated plans and records every semantic change by content hash.

**Tech Stack:** Python frozen dataclasses, JSON/JSON Schema-style validation without runtime network access, pytest, canonical SHA-256, existing Typed AST/Logical IR, pandas official-workbook evidence.

---

### Task 1: Registry model, schema, and grounded catalog

**Files:**
- Create: `configs/official/indicators.schema.json`
- Create: `configs/official/indicators.json`
- Create: `src/findsl/official/registry.py`
- Test: `tests/official/domain/test_registry.py`

- [ ] Write failing tests for valid loading, aliases, immutable cached results, unknown fields, duplicate aliases, invalid scale/type combinations, missing-domain physical hints, and compatibility with `_resolve_indicator_meta`.
- [ ] Run the focused test and verify RED due to missing module/configuration.
- [ ] Implement frozen definitions, deterministic validation, alias index, cache, and the initial catalog covering every currently grounded official indicator.
- [ ] Run focused and strict compiler tests; commit `feat: add official indicator registry`.

### Task 2: Domain expression and relation nodes

**Files:**
- Create: `src/findsl/official/domain/__init__.py`
- Create: `src/findsl/official/domain/expressions.py`
- Modify: `src/findsl/official/ir/relational.py`
- Modify: `src/findsl/official/ir/validate.py`
- Test: `tests/official/domain/test_domain_ir.py`

- [ ] Write failing tests for canonical indicator, market, date, event, consecutive, exist, rank and requirement nodes, plus domain relation validation and `LogicalEmpty` boundaries.
- [ ] Implement immutable SQL-free nodes, deterministic JSON/hash, and relation validator support.
- [ ] Verify physical names/SQL snippets are rejected; commit `feat: define official domain IR`.

### Task 3: Typed-slot domain binder and diagnostics

**Files:**
- Create: `src/findsl/official/domain/binder.py`
- Test: `tests/official/domain/test_binder.py`

- [ ] Write failing goldens for all 12 function signatures and negatives for unknown indicators, missing domains, invalid direction/date/count expression and unsupported slot combinations.
- [ ] Implement structured `DomainDiagnostic`, indicator binding, market/date normalization, event/rank binding, count-expression classification and data requirements.
- [ ] Confirm missing data never becomes Empty or a successful binding; commit `feat: bind official functions to domain IR`.

### Task 4: Integrate domain binding with logical lowering

**Files:**
- Modify: `src/findsl/official/lowering.py`
- Test: `tests/official/domain/test_domain_lowering.py`

- [ ] Write failing tests that known calls become domain expressions/relations while unsupported data domains return precise codes.
- [ ] Add optional domain binding to lowering, preserve Phase 3 generic shadow mode, and validate every successful domain plan.
- [ ] Run Phase 3 evidence regression and commit `feat: lower official domain semantics`.

### Task 5: Deterministic optimizer framework and safe rules

**Files:**
- Create: `src/findsl/official/optimizer/base.py`
- Create: `src/findsl/official/optimizer/rules.py`
- Create: `src/findsl/official/optimizer/engine.py`
- Test: `tests/official/optimizer/test_engine.py`
- Test: `tests/official/optimizer/test_rules.py`

- [ ] Write RED tests for rule enable/disable, trace hashes, deterministic order, rollback on failure, idempotence, boolean constant folding, predicate dedup/filter merge, limit normalization and safe stage handling.
- [ ] Implement bounded fixed-batch optimization and each rule with explicit preconditions and proof obligation text.
- [ ] Revalidate after every changed batch and commit rules in independently testable groups.

### Task 6: Small-data equivalence interpreter

**Files:**
- Create: `src/findsl/official/optimizer/interpreter.py`
- Test: `tests/official/optimizer/test_equivalence.py`

- [ ] Write fixtures and failing tests comparing pre/post plans for filter, constants, duplicate predicates, limits and empty relations.
- [ ] Implement a deliberately small logical interpreter independent of SQL generation.
- [ ] Require exact row-key equality for production rules; commit `test: prove logical rewrite equivalence`.

### Task 7: Official domain and optimizer evidence

**Files:**
- Create: `src/findsl/official_domain_evidence.py`
- Modify: `src/findsl/cli.py`
- Test: `tests/test_official_domain_evidence.py`

- [ ] Write tests for 5,799-row classification, registry/alias hits, missing domains, precise binder errors, domain nodes, rewrite hits, validation, idempotence, latency and protected Phase 1-3 floors.
- [ ] Implement `official-domain-evidence` and single-query `official-slot-optimize` commands.
- [ ] Generate `reports/phase4_official_domain_evidence.json/md`, inspect every blocking category, and commit code/tests.

### Task 8: Documentation, complete verification, evidence archive, and push

**Files:**
- Create: `docs/39_领域IR注册表与规则优化器说明.md`
- Modify: `README.md`
- Create: `reports/phase4_official_domain_evidence.json`
- Create: `reports/phase4_official_domain_evidence.md`

- [ ] Explain registry extension, domain diagnostics, rule traces, equivalence limits and evidence boundaries in Chinese.
- [ ] Run generated-source check, all tests, official evidence, whitespace audit and clean-status audit.
- [ ] Bind evidence to the final implementation commit, force-add ignored reports, push through `127.0.0.1:7897`, and verify remote HEAD equality.
