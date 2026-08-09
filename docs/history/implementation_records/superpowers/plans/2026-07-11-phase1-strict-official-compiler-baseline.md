# Strict Official Compiler Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为官方槽位 DSL 建立 strict/recovery 双模式、精确函数签名与类型检查，并将“严格成功”与“容错/降级”从证据口径上分离。

**Architecture:** 新建 `findsl.official` 包承载策略、诊断、签名与语义分析，现有 `official_slot.py` 保持兼容门面。本阶段不替换 parser 和 SQL generator，但在 SQL 生成前强制通过新语义分析，并让容错修复可见。

**Tech Stack:** Python 3.9+、dataclasses、Enum、pytest、pandas（官方工作簿审计）。

---

## File Structure

- Create `src/findsl/official/__init__.py`: 官方编译子系统公开 API。
- Create `src/findsl/official/policy.py`: `CompileMode` 和编译策略。
- Create `src/findsl/official/diagnostics.py`: 结构化诊断和源文本修复记录。
- Create `src/findsl/official/signatures.py`: 12 类官方函数的精确参数数量和返回类型。
- Create `src/findsl/official/semantics.py`: AST 类型推导和运算符检查。
- Modify `src/findsl/official_slot.py`: 容错结果可见、编译模式可选、生成 SQL 前运行语义分析。
- Modify `src/findsl/cli.py`: `official-slot-parse/compile/coverage` 增加 strict/recovery 选项。
- Modify `tests/test_official_slot.py`: 新增严格解析、参数数量、类型不匹配和覆盖率口径测试。
- Create `tests/test_official_semantics.py`: 语义分析器聚焦测试。

### Task 1: Compile policy and diagnostics

**Files:**
- Create: `src/findsl/official/__init__.py`
- Create: `src/findsl/official/policy.py`
- Create: `src/findsl/official/diagnostics.py`
- Test: `tests/test_official_semantics.py`

- [ ] **Step 1: Write the failing policy and diagnostic tests**

```python
from findsl.official import CompileMode, SourceRepair


def test_compile_mode_parses_cli_values():
    assert CompileMode.parse("strict") is CompileMode.STRICT
    assert CompileMode.parse("recovery") is CompileMode.RECOVERY


def test_source_repair_serializes_for_evidence():
    repair = SourceRepair(code="TRAILING_QUOTE", message="remove trailing quote", position=12)
    assert repair.to_dict() == {
        "code": "TRAILING_QUOTE",
        "message": "remove trailing quote",
        "position": 12,
    }
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_official_semantics.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'findsl.official'`.

- [ ] **Step 3: Implement the minimal policy and diagnostic models**

```python
class CompileMode(str, Enum):
    STRICT = "strict"
    RECOVERY = "recovery"

    @classmethod
    def parse(cls, value: str) -> "CompileMode":
        try:
            return cls(str(value).lower())
        except ValueError as exc:
            raise ValueError(f"Unsupported official compile mode: {value}") from exc
```

`SourceRepair` is a frozen dataclass with `code/message/position` and `to_dict()`.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m pytest tests/test_official_semantics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official tests/test_official_semantics.py
git commit -m "feat: add official compiler policies and diagnostics"
```

### Task 2: Observable strict and recovery parsing

**Files:**
- Modify: `src/findsl/official_slot.py:584-882`
- Test: `tests/test_official_slot.py`

- [ ] **Step 1: Write failing tests for strict and recovery behavior**

```python
def test_strict_parse_rejects_leading_boolean_operator():
    with pytest.raises(OfficialSlotError) as excinfo:
        parse_official_slot("and indicator('', '', '涨停', '', '', '', '') = True", mode="strict")
    assert excinfo.value.code == "OFFICIAL_PARSE_ERROR"


def test_recovery_parse_reports_leading_operator_repair():
    parsed = parse_official_slot_with_diagnostics(
        "and indicator('', '', '涨停', '', '', '', '') = True",
        mode="recovery",
    )
    assert parsed.repairs[0].code == "LEADING_BOOLEAN_OPERATOR"
    assert parsed.normalized_source.startswith("indicator(")
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_official_slot.py -q -k "strict_parse or recovery_parse"`

Expected: FAIL because `mode` and `parse_official_slot_with_diagnostics` do not exist.

- [ ] **Step 3: Implement source normalization as a structured result**

Add a frozen `OfficialParseResult` with `source`, `normalized_source`, `ast`, and `repairs`. Replace `_sanitize_official_slot_source()` internals with helpers that append repair codes for:

```text
LEADING_BOOLEAN_OPERATOR
DANGLING_EDGE_QUOTE
ORPHAN_LITERAL_QUOTED
UNMATCHED_CLOSING_PAREN
```

`strict` passes the original string directly to the lexer. `recovery` uses the normalized string. Keep `parse_official_slot()` returning the AST for backward compatibility.

- [ ] **Step 4: Run focused and legacy parser tests**

Run: `python -m pytest tests/test_official_slot.py -q -k "strict_parse or recovery_parse or parse_official"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official_slot.py tests/test_official_slot.py
git commit -m "feat: separate strict and recovery official parsing"
```

### Task 3: Exact official function signatures

**Files:**
- Create: `src/findsl/official/signatures.py`
- Modify: `src/findsl/official/__init__.py`
- Test: `tests/test_official_semantics.py`

- [ ] **Step 1: Write failing signature tests**

```python
from findsl.official import OFFICIAL_FUNCTION_SIGNATURES


def test_all_twelve_official_functions_have_exact_signatures():
    assert set(OFFICIAL_FUNCTION_SIGNATURES) == {
        "indicator", "rank", "belong_industry", "queryData",
        "cross_above", "cross_down", "close_together", "reset",
        "golden_cross", "record_high", "record_low", "position",
    }
    assert OFFICIAL_FUNCTION_SIGNATURES["indicator"].arity == 7
    assert OFFICIAL_FUNCTION_SIGNATURES["rank"].arity == 8
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_official_semantics.py -q -k signatures`

Expected: FAIL because the registry does not exist.

- [ ] **Step 3: Implement immutable signatures**

Create `FunctionSignature(name, slots, result_kind)` and declare the exact slot order from the official specification. Use result kinds `dynamic`, `numeric`, `boolean`, and `string`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_official_semantics.py -q -k signatures`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official/signatures.py src/findsl/official/__init__.py tests/test_official_semantics.py
git commit -m "feat: declare exact official function signatures"
```

### Task 4: Typed semantic analyzer

**Files:**
- Create: `src/findsl/official/semantics.py`
- Modify: `src/findsl/official_slot.py:886-905`
- Test: `tests/test_official_semantics.py`

- [ ] **Step 1: Write failing type and arity tests**

```python
def test_semantics_rejects_extra_indicator_argument():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '收盘价', '', '', '', '', 'EXTRA') > 1"
        )
    assert excinfo.value.code == "OFFICIAL_SLOT_ARITY_ERROR"


def test_semantics_rejects_numeric_string_comparison():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '收盘价', '', '', '', '') > 'abc'"
        )
    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_official_semantics.py -q -k "extra_indicator or numeric_string"`

Expected: both tests FAIL because the current compiler accepts the DSL.

- [ ] **Step 3: Implement AST type inference**

`OfficialSemanticAnalyzer.validate(ast)` must:

- require exact arity for all 12 functions;
- require every slot argument to be an `OfficialLiteral` containing a string;
- derive `indicator/queryData/belong_industry` type from `_resolve_indicator_meta`;
- return boolean for cross/reset/record functions, string for position, numeric for rank;
- require arithmetic operands to be numeric;
- require ordered comparisons to use compatible numeric/time types;
- allow equality for matching types and unknown indicators to continue to the existing grounded-data diagnostic.

Integrate the analyzer immediately after parsing and before `_compile_query()`.

- [ ] **Step 4: Verify focused tests and all official slot tests**

Run: `python -m pytest tests/test_official_semantics.py tests/test_official_slot.py -q`

Expected: PASS. If legacy tests contain malformed arity that was previously ignored, change those fixtures only when the official function prototype proves them invalid.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official/semantics.py src/findsl/official_slot.py tests/test_official_semantics.py tests/test_official_slot.py
git commit -m "feat: enforce typed semantics for official DSL"
```

### Task 5: Strict compiler result and degraded-semantics gate

**Files:**
- Modify: `src/findsl/official_slot.py:145-165,886-905`
- Modify: `src/findsl/cli.py:19-37,197-267`
- Test: `tests/test_official_slot.py`

- [ ] **Step 1: Write failing strict compiler tests**

```python
def test_strict_compile_rejects_runtime_date_fallback():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler(mode="strict").compile(
            "indicator('', '', '收盘价', '收盘后', '', '', '') > 1"
        )
    assert excinfo.value.code == "OFFICIAL_DEGRADED_SEMANTICS"


def test_recovery_compile_exposes_repairs_and_warnings():
    result = OfficialSlotCompiler(mode="recovery").compile(
        "and indicator('', '', '收盘价', '收盘后', '', '', '') > 1"
    )
    assert result.repairs
    assert result.warnings
    assert result.strict_success is False
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_official_slot.py -q -k "strict_compile or recovery_compile_exposes"`

Expected: FAIL because compiler mode and result fields are missing.

- [ ] **Step 3: Implement strict success rules**

Extend `OfficialCompileResult` with `normalized_source`, `repairs`, `strict_success`, and `degraded`. In strict mode, any warning, recovery repair, generated `1=0`, or generated `1=1` raises `OFFICIAL_DEGRADED_SEMANTICS`. Recovery mode returns the diagnostics without raising.

Add `--mode {strict,recovery}` to parse/compile/coverage commands. Preserve `recovery` as CLI default during migration.

- [ ] **Step 4: Verify CLI and compiler tests**

Run: `python -m pytest tests/test_official_slot.py tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official_slot.py src/findsl/cli.py tests/test_official_slot.py tests/test_cli.py
git commit -m "feat: gate degraded official SQL in strict mode"
```

### Task 6: Rebuild workbook coverage metrics

**Files:**
- Modify: `src/findsl/official_slot.py:3463-3683`
- Test: `tests/test_official_slot.py:1046-1085`

- [ ] **Step 1: Write failing coverage metric assertions**

```python
def test_workbook_coverage_separates_strict_recovery_and_degraded_rows():
    coverage = compile_training_workbook(OFFICIAL_WORKBOOK, sample_size=5)
    assert coverage["recovery_parse_ok"] == 5799
    assert coverage["strict_parse_failed"] >= 7
    assert coverage["strict_compile_ok"] < coverage["recovery_compile_ok"]
    assert coverage["degraded_rows"] > 0
    assert coverage["sql_true_fallback_rows"] > 0
    assert coverage["sql_false_fallback_rows"] > 0
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_official_slot.py -q -k workbook_coverage_separates`

Expected: FAIL because the new counters are missing.

- [ ] **Step 3: Implement truthful coverage accounting**

For every workbook row, collect strict parse, recovery parse, recovery repairs, recovery compile, warning/degraded status, strict compile, `1=0`, and `1=1` separately. Keep legacy keys `parse_ok` and `compile_ok` during one compatibility cycle, but label them as recovery metrics in Markdown.

- [ ] **Step 4: Verify coverage report generation**

Run: `python -m pytest tests/test_official_slot.py -q -k "workbook_coverage or coverage_cli"`

Expected: PASS and Markdown contains both strict and recovery columns.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official_slot.py tests/test_official_slot.py
git commit -m "feat: separate strict and recovery coverage evidence"
```

### Task 7: Correct official CSV date profiling

**Files:**
- Modify: `src/findsl/official_slot.py:3535-3566`
- Test: `tests/test_official_slot.py`

- [ ] **Step 1: Write a failing unsorted-date profile test**

```python
def test_csv_profile_uses_true_min_and_max_dates(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("mktcode,bizdate\n0,2020-02-01\n0,2019-01-01\n0,2021-03-01\n", encoding="utf-8")
    profile = _profile_csv(path)
    assert profile["first_date"] == "2019-01-01"
    assert profile["last_date"] == "2021-03-01"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_official_slot.py -q -k true_min_and_max_dates`

Expected: FAIL with `first_date == '2020-02-01'`.

- [ ] **Step 3: Track lexical min/max while streaming**

For ISO dates, update:

```python
if value:
    first_date = value if not first_date else min(first_date, value)
    last_date = value if not last_date else max(last_date, value)
```

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_official_slot.py -q -k true_min_and_max_dates`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/findsl/official_slot.py tests/test_official_slot.py
git commit -m "fix: report true official CSV date ranges"
```

### Task 8: Phase verification and evidence documentation

**Files:**
- Create: `docs/36_严格官方编译基线与口径说明.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_official_semantics.py tests/test_official_slot.py tests/test_cli.py -q`

Expected: all focused tests pass.

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest`

Expected: all tests pass; record the exact count and elapsed time. The known Windows temporary-directory cleanup message is documented separately and must not be represented as a test failure.

- [ ] **Step 3: Regenerate a temporary coverage report for inspection**

Run:

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage --workbook '<official-workbook>' --mode recovery --json-output reports/phase1_official_coverage.json --report-output reports/phase1_official_coverage.md
```

Expected: report contains strict parse, recovery parse, strict compile, recovery compile, degraded rows, repair rows, `1=0`, and `1=1` counters.

- [ ] **Step 4: Document changed evidence semantics**

The new Chinese document must explain that historical `compile_ok=1882` is recovery compilation, not SQL accuracy, and that subsequent score claims use strict executable cases only.

- [ ] **Step 5: Commit**

```bash
git add docs/36_严格官方编译基线与口径说明.md CHANGELOG.md
git commit -m "docs: define strict official compiler evidence policy"
```

