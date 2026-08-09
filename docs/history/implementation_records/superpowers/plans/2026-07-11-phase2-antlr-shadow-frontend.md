# Phase 2 ANTLR Shadow Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible ANTLR4 Python frontend that maps official DSL into the stable AST, emits source-grounded diagnostics, and proves parity against the handwritten parser on all 5,799 official rows before any default switch.

**Architecture:** Keep `official_slot.py` as the compatibility facade and current behavioral baseline. Add a bounded `findsl.official.frontend` package containing common outcomes, an ANTLR adapter, a handwritten adapter, and shadow comparison; generated ANTLR files are isolated and reproducibly rebuilt from one source grammar.

**Tech Stack:** Python 3.9+, ANTLR 4.13.2, `antlr4-python3-runtime`, pytest, openpyxl/pandas for official workbook evidence, Git-based generated-source verification.

---

## File map

- Create `grammar/OfficialSlot.g4`: production grammar and single source of truth.
- Create `tools/antlr/antlr-4.13.2-complete.jar.sha256`: pinned generator checksum.
- Create `scripts/generate_antlr.py`: deterministic generator bootstrap and invocation.
- Modify `pyproject.toml`: runtime/dev dependencies and generated package inclusion.
- Create `src/findsl/official/frontend/protocol.py`: spans, diagnostics, outcomes, frontend enum/protocol.
- Create `src/findsl/official/frontend/handwritten.py`: adapter around current parser.
- Create `src/findsl/official/frontend/antlr_frontend.py`: lexer/parser/error listener orchestration.
- Create `src/findsl/official/frontend/ast_adapter.py`: parse-tree visitor and source map.
- Create `src/findsl/official/frontend/shadow.py`: normalized AST comparison and report model.
- Create `src/findsl/official/frontend/generated/*`: generated lexer/parser/visitor.
- Modify `src/findsl/official_slot.py`: frontend-selecting compatibility entry point only.
- Modify `src/findsl/cli.py`: explicit `--frontend` and shadow evidence command.
- Create `tests/official/frontend/*`: focused grammar, adapter, diagnostic, parity, generation tests.
- Create `src/findsl/official_frontend_evidence.py`: workbook parity and latency evidence.
- Create `docs/37_ANTLR影子前端与迁移证据.md`: factual Chinese implementation and evidence guide.

### Task 1: Pin ANTLR toolchain and deterministic generation

**Files:**
- Create: `grammar/OfficialSlot.g4`
- Create: `scripts/generate_antlr.py`
- Create: `tools/antlr/antlr-4.13.2-complete.jar.sha256`
- Modify: `pyproject.toml`
- Test: `tests/official/frontend/test_generated_sources.py`

- [ ] **Step 1: Write the failing toolchain test**

```python
def test_antlr_runtime_and_generated_versions_match():
    from antlr4 import RuntimeMetaData
    from findsl.official.frontend.generated.OfficialSlotParser import OfficialSlotParser
    assert RuntimeMetaData.VERSION == "4.13.2"
    assert "4.13.2" in OfficialSlotParser.__doc__ or OfficialSlotParser.grammarFileName == "OfficialSlot.g4"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/official/frontend/test_generated_sources.py -v`
Expected: collection/import failure because runtime and generated package do not exist.

- [ ] **Step 3: Add pinned dependencies and generator**

Add `antlr4-python3-runtime==4.13.2` to project dependencies. The script downloads only the pinned jar through the configured proxy when absent, verifies the recorded SHA-256, invokes `java -jar ... -Dlanguage=Python3 -visitor -no-listener`, normalizes generated output location, and exits nonzero on checksum or Java failure.

- [ ] **Step 4: Generate and verify GREEN**

Run: `python scripts/generate_antlr.py && python -m pytest tests/official/frontend/test_generated_sources.py -v`
Expected: PASS and generated files under `src/findsl/official/frontend/generated`.

- [ ] **Step 5: Commit**

```powershell
git add grammar scripts/generate_antlr.py tools/antlr pyproject.toml src/findsl/official/frontend/generated tests/official/frontend/test_generated_sources.py
git commit -m "build: add reproducible ANTLR frontend generation"
```

### Task 2: Define stable frontend protocol and source spans

**Files:**
- Create: `src/findsl/official/frontend/__init__.py`
- Create: `src/findsl/official/frontend/protocol.py`
- Test: `tests/official/frontend/test_protocol.py`

- [ ] **Step 1: Write failing immutable-model tests**

```python
def test_parse_outcome_serializes_grounded_diagnostic():
    span = SourceSpan(0, 3, 1, 1, 1, 4, "abc")
    diagnostic = FrontendDiagnostic("OFFICIAL_ANTLR_PARSE_ERROR", Severity.ERROR, "bad", span, "antlr")
    outcome = ParseOutcome(None, (diagnostic,), "abc", "abc", (), "antlr", 7)
    assert outcome.ok is False
    assert outcome.to_dict()["diagnostics"][0]["span"]["end_offset"] == 3
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/official/frontend/test_protocol.py -v`
Expected: import failure for undefined protocol models.

- [ ] **Step 3: Implement frozen dataclasses and protocol**

Define `SourceSpan`, `FrontendDiagnostic`, `ParseOutcome`, `FrontendName`, `Severity`, and `OfficialFrontend` protocol. Validate half-open offsets and expose deterministic `to_dict()` methods without serializing AST object addresses.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/official/frontend/test_protocol.py -v`
Expected: PASS.

```powershell
git add src/findsl/official/frontend tests/official/frontend/test_protocol.py
git commit -m "feat: define stable official frontend protocol"
```

### Task 3: Parse valid DSL and adapt ANTLR trees to stable AST

**Files:**
- Create: `src/findsl/official/frontend/ast_adapter.py`
- Create: `src/findsl/official/frontend/antlr_frontend.py`
- Test: `tests/official/frontend/test_ast_adapter.py`
- Test: `tests/official/frontend/test_antlr_grammar.py`

- [ ] **Step 1: Write failing golden AST tests**

```python
@pytest.mark.parametrize("source", [
    "indicator('', '', '涨幅', '今日', '', '', '') > 5%",
    "a + b * 2 >= 3 and c between [1, 4)",
    "a = 1 then rank('', '', '涨幅', 'desc', '今日', '', '', '') <= 10 limit 0,20",
])
def test_antlr_ast_matches_handwritten_ast(source):
    assert AntlrOfficialFrontend().parse(source).ast.to_dict() == parse_official_slot(source).to_dict()
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/official/frontend/test_ast_adapter.py tests/official/frontend/test_antlr_grammar.py -v`
Expected: failure because adapter/frontend are undefined.

- [ ] **Step 3: Implement visitor without reparsing source**

Map every grammar rule directly to `OfficialLiteral`, `OfficialIdentifier`, `OfficialFunctionCall`, `OfficialBinaryOp`, `OfficialComparison`, `OfficialRangeLiteral`, and `OfficialLimit`. Preserve precedence, left associativity, percentage semantics, quote decoding, and case-normalized boolean values. Store node spans in `SourceMap` keyed by node identity.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/official/frontend/test_ast_adapter.py tests/official/frontend/test_antlr_grammar.py -v`
Expected: PASS.

```powershell
git add src/findsl/official/frontend tests/official/frontend/test_ast_adapter.py tests/official/frontend/test_antlr_grammar.py
git commit -m "feat: adapt ANTLR parse trees to official AST"
```

### Task 4: Reject ANTLR recovery trees and emit exact diagnostics

**Files:**
- Modify: `src/findsl/official/frontend/antlr_frontend.py`
- Modify: `src/findsl/official/frontend/protocol.py`
- Test: `tests/official/frontend/test_diagnostics.py`

- [ ] **Step 1: Write failing invalid-input tests**

```python
@pytest.mark.parametrize("source,code", [
    ("a =", "OFFICIAL_ANTLR_PARSE_ERROR"),
    ("a @ 1", "OFFICIAL_ANTLR_LEX_ERROR"),
    ("indicator('x)", "OFFICIAL_ANTLR_LEX_ERROR"),
])
def test_syntax_recovery_never_returns_success(source, code):
    outcome = AntlrOfficialFrontend().parse(source)
    assert outcome.ast is None
    assert outcome.diagnostics[0].code == code
    assert outcome.diagnostics[0].span.fragment
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/official/frontend/test_diagnostics.py -v`
Expected: at least one invalid input incorrectly returns an AST or lacks grounded location.

- [ ] **Step 3: Implement lexer/parser listeners and error gate**

Remove console listeners, attach separate lexer and parser listeners, convert zero-based ANTLR positions to one-based user coordinates, clamp offsets, and refuse adapter execution whenever either listener captured an error. Catch adapter failures under `OFFICIAL_ANTLR_ADAPTER_ERROR` without hiding programming exceptions outside the adapter boundary.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/official/frontend/test_diagnostics.py -v`
Expected: PASS with no stderr noise.

```powershell
git add src/findsl/official/frontend tests/official/frontend/test_diagnostics.py
git commit -m "feat: add source-grounded ANTLR diagnostics"
```

### Task 5: Wrap handwritten parser and preserve strict/recovery policy

**Files:**
- Create: `src/findsl/official/frontend/handwritten.py`
- Modify: `src/findsl/official_slot.py`
- Test: `tests/official/frontend/test_handwritten_frontend.py`
- Test: `tests/official/frontend/test_modes.py`

- [ ] **Step 1: Write failing compatibility tests**

```python
def test_recovery_repairs_are_frontend_independent():
    source = "and indicator('', '', '涨幅', '', '', '', '') > 1"
    old = parse_official_slot_with_diagnostics(source, mode="recovery")
    new = parse_official_slot_with_diagnostics(source, mode="recovery", frontend="antlr")
    assert new.ast.to_dict() == old.ast.to_dict()
    assert new.repairs == old.repairs

def test_strict_antlr_does_not_repair_source():
    with pytest.raises(OfficialSlotError):
        parse_official_slot(source, mode="strict", frontend="antlr")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/official/frontend/test_handwritten_frontend.py tests/official/frontend/test_modes.py -v`
Expected: unexpected keyword argument `frontend`.

- [ ] **Step 3: Implement selection behind compatibility facade**

Add `frontend="handwritten"` as a backward-compatible keyword. Run existing source normalization exactly once before the selected parser. Convert blocking `ParseOutcome` diagnostics into stable `OfficialSlotError`, preserving legacy default behavior and CLI JSON shape.

- [ ] **Step 4: Verify GREEN plus legacy parser suite and commit**

Run: `python -m pytest tests/official/frontend tests/test_official_slot.py -v`
Expected: all pass; official workbook recovery remains 5,799.

```powershell
git add src/findsl/official/frontend/handwritten.py src/findsl/official_slot.py tests/official/frontend
git commit -m "feat: select official parser frontend compatibly"
```

### Task 6: Add shadow comparison with privacy-safe divergence records

**Files:**
- Create: `src/findsl/official/frontend/shadow.py`
- Test: `tests/official/frontend/test_shadow_parity.py`

- [ ] **Step 1: Write failing comparison tests**

```python
def test_shadow_match_uses_canonical_ast_and_hash():
    comparison = compare_frontends("a = 1")
    assert comparison.classification == "MATCH"
    assert len(comparison.input_sha256) == 64
    assert comparison.source is None

def test_first_ast_difference_has_json_path():
    diff = first_ast_difference({"op": "and"}, {"op": "or"})
    assert diff.path == "$.op"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/official/frontend/test_shadow_parity.py -v`
Expected: import failure for shadow comparison API.

- [ ] **Step 3: Implement six-state classification**

Implement `MATCH`, `AST_MISMATCH`, `ANTLR_REJECTED`, `HANDWRITTEN_REJECTED`, `ERROR_MATCH`, and `ERROR_MISMATCH`; include input SHA-256, elapsed timings, diagnostics, and first JSON-path difference. Full source is omitted unless `include_source=True`.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/official/frontend/test_shadow_parity.py -v`
Expected: PASS.

```powershell
git add src/findsl/official/frontend/shadow.py tests/official/frontend/test_shadow_parity.py
git commit -m "feat: compare official parser frontends in shadow mode"
```

### Task 7: Produce official-workbook parity and latency evidence

**Files:**
- Create: `src/findsl/official_frontend_evidence.py`
- Modify: `src/findsl/cli.py`
- Test: `tests/test_official_frontend_evidence.py`

- [ ] **Step 1: Write failing evidence aggregation test**

```python
def test_evidence_counts_classifications_and_percentiles(tmp_path):
    report = build_frontend_evidence(WORKBOOK, sample_size=3)
    assert report["row_count"] == 5799
    assert sum(report["classifications"].values()) == 5799
    assert report["input_sha256"]
    assert report["latency_ms"]["antlr"]["p95"] >= 0
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_official_frontend_evidence.py -v`
Expected: module/command does not exist.

- [ ] **Step 3: Implement streaming aggregation and CLI**

Add `official-frontend-evidence --workbook --json-output --report-output --sample-size`. Aggregate all rows without storing every AST, retain bounded samples per mismatch class, compute nearest-rank P50/P95 from nanosecond samples, record runtime/generator versions, Git HEAD when available, and input SHA-256.

- [ ] **Step 4: Run official evidence and resolve every mismatch**

Run:

```powershell
python -m findsl.cli official-frontend-evidence --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports/phase2_frontend_evidence.json --report-output reports/phase2_frontend_evidence.md
```

Expected final gate: recovery rows `5799`, strict rows `5792`, successful dual parses classified `MATCH`, no unexplained `AST_MISMATCH`; any intentionally different invalid-input diagnostics are enumerated and justified.

- [ ] **Step 5: Verify tests and commit**

Run: `python -m pytest tests/test_official_frontend_evidence.py tests/official/frontend -v`
Expected: PASS.

```powershell
git add src/findsl/official_frontend_evidence.py src/findsl/cli.py tests/test_official_frontend_evidence.py reports/phase2_frontend_evidence.json reports/phase2_frontend_evidence.md
git commit -m "feat: add official ANTLR parity evidence"
```

### Task 8: Document, regenerate, run full verification, and push

**Files:**
- Create: `docs/37_ANTLR影子前端与迁移证据.md`
- Modify: `README.md`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Write factual Chinese documentation**

Document architecture, generation command, frontend modes, error codes, evidence interpretation, rollback, and the explicit statement that parser parity does not prove financial semantic correctness. Add a Windows/Linux-compatible CI job that installs the project with dev dependencies, verifies generated sources, and runs the complete test suite.

- [ ] **Step 2: Verify reproducibility and complete suite**

Run:

```powershell
python scripts/generate_antlr.py --check
python -m pytest -q
git diff --check
git status --short
```

Expected: generator check passes, full suite exits 0, no whitespace errors, only intended evidence/document changes remain.

- [ ] **Step 3: Audit spec coverage**

Confirm fixed versions, isolated generation, stable AST, source spans, strict/recovery behavior, explicit frontend selection, 5,799/5,792 gates, mismatch evidence, full tests, and latency percentiles are all represented by code plus tests.

- [ ] **Step 4: Commit and push through proxy**

```powershell
git add README.md docs .github
git commit -m "docs: publish ANTLR frontend migration evidence"
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
$env:ALL_PROXY='socks5://127.0.0.1:7897'
git push origin feat/antlr-calcite-architecture
```

Expected: remote branch HEAD equals local HEAD.
