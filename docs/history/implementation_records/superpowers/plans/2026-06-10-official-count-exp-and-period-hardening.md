# Official Count Expression and Period Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground more official real-data DSL cases by supporting rank ranges, expression-level `count_exp`, period-function `count_exp`, and stricter consecutive-run SQL.

**Architecture:** Keep all behavior inside `src/findsl/official_slot.py`. Add small compiler helpers that detect count expressions in a comparison, rewrite the full comparison into an aliased window predicate, and reuse existing indicator/period/rank compilation paths with `count_exp` stripped only inside the predicate.

**Tech Stack:** Python 3.9, pytest, Apache Doris-compatible SQL, official A-share CSV schema.

---

## Execution Record

Implemented on 2026-06-10. Targeted red tests failed first, then passed after compiler changes. Official slot coverage improved from 1,824 to 1,844 compiled rows. `UNSUPPORTED_OFFICIAL_COUNT_EXP` fell from 56 to 45, and `UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION` fell from 18 to 1. Remaining unsupported cases are intentionally preserved where the official three-table dataset lacks the required source fields or time granularity.

---

### Task 1: Rank Between and Percent Range

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify: `src/findsl/official_slot.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

```python
def test_compile_rank_between_top_level_condition():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '收盘价', 'desc', '今天', '', '', '') between '[5,10]'"
    )

    assert "ROW_NUMBER() OVER" in result.sql
    assert "ranked.rank_no >= 5" in result.sql
    assert "ranked.rank_no <= 10" in result.sql


def test_compile_rank_count_exp_between_percent_uses_partition_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '市盈率', 'desc', '近15天', '', '', 'CONS=3日') between '[5%,10%]'"
    )

    assert "COUNT(*) OVER (PARTITION BY DATE_TRUNC(rb.bizdate, 'day')) AS partition_count" in result.sql
    assert "CEIL((ranked.partition_count * 5) / 100.0)" in result.sql
    assert "CEIL((ranked.partition_count * 10) / 100.0)" in result.sql
    assert "ranked.rank_no >=" in result.sql
    assert "ranked.rank_no <=" in result.sql
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests\test_official_slot.py::test_compile_rank_between_top_level_condition tests\test_official_slot.py::test_compile_rank_count_exp_between_percent_uses_partition_count -q
```

Expected: fail because rank `between` is not accepted in top-level rank filters/count-exp rank filters.

- [ ] **Step 3: Implement**

Extend `_is_rank_filter_comparison` to include `between`. Add `_rank_no_predicate` reuse to top-level rank paths. Add partition count when rank range uses percent literals.

- [ ] **Step 4: Verify GREEN**

Run the same pytest command and expect both tests to pass.

### Task 2: Expression-Level Count Expression

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify: `src/findsl/official_slot.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

```python
def test_compile_count_exp_inside_arithmetic_expression_uses_window_predicate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('沪', '', '内盘', '近5周', '', '', 'EXIST>6日') "
        "/ indicator('沪', '', '每手股数', '近5周', '', '', 'EXIST>6日') > 2000"
    )

    assert "FROM newzl.hsj_stock_hq_basic AS wb" in result.sql
    assert "(wb.innerVol / 100) > 2000" in result.sql
    assert ") > 6" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_count_exp_expression_supports_indicator_to_indicator_comparison():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '收盘价', '近三十天', '', '', 'CONS=4日') "
        ">= indicator('', '', '5日均线', '近三十天', '', '', 'CONS=4日')"
    )

    assert "(wb.closePx / 10000.0) >= wt.ma5" in result.sql
    assert "MAX(run_length)" in result.sql
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests\test_official_slot.py::test_compile_count_exp_inside_arithmetic_expression_uses_window_predicate tests\test_official_slot.py::test_compile_count_exp_expression_supports_indicator_to_indicator_comparison -q
```

Expected: fail because `indicator(..., count_exp)` currently must be the direct left side of a comparison.

- [ ] **Step 3: Implement**

Add helpers:

```python
_comparison_count_exp_rule(node)
_expr_sql_ignoring_count_exp(node, warnings, aliases)
_count_exp_window_predicate_sql(node, rule, warnings)
```

Only support comparisons where all count expressions share the same `count_exp` and compatible date/market/select scope. Strip `count_exp` only inside the per-row predicate.

- [ ] **Step 4: Verify GREEN**

Run the same pytest command and expect pass.

### Task 3: Strict Consecutive-Run SQL

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify: `src/findsl/official_slot.py`

- [ ] **Step 1: Write failing test**

Add:

```python
def test_compile_cons_count_exp_uses_longest_run_not_plain_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨幅', '近5日', '', '', 'CONS=3日') > 5%"
    )

    assert "ROW_NUMBER() OVER (ORDER BY matched.bizdate)" in result.sql
    assert "DATEDIFF(matched.bizdate" in result.sql
    assert "MAX(run_length) >= 3" in result.sql
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests\test_official_slot.py::test_compile_cons_count_exp_uses_longest_run_not_plain_count -q
```

Expected: fail because current SQL uses a plain threshold count for `CONS=3日`.

- [ ] **Step 3: Implement**

Add a shared `_count_exp_subquery_sql(inner_from_sql, predicate, rule)` helper. For `CONS` with a numeric count and date/day granularity, emit matched-date grouping with `DATEDIFF(date, DATE '1970-01-01') - ROW_NUMBER()` and `MAX(run_length)`.

- [ ] **Step 4: Verify GREEN**

Run the same pytest command and expect pass.

### Task 4: Period Function Count Expression

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify: `src/findsl/official_slot.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
def test_compile_position_count_exp_window_predicate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "position('', '', '最新价', '10日', '近5日', '', '', 'CONS=3日') = '低'"
    )

    assert "CASE WHEN" in result.sql
    assert "MAX(run_length) >= 3" in result.sql
    assert "= '低'" in result.sql


def test_compile_record_high_count_exp_window_predicate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "record_high('', '', '最高价', '120日', '近5日', '', '', 'EXIST>=2日') = True"
    )

    assert "ext.pxMkTopDays >= 120" in result.sql
    assert ") >= 2" in result.sql
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests\test_official_slot.py::test_compile_position_count_exp_window_predicate tests\test_official_slot.py::test_compile_record_high_count_exp_window_predicate -q
```

Expected: fail because period functions with `count_exp` are currently rejected.

- [ ] **Step 3: Implement**

In `_comparison_sql`, detect direct period function comparisons with `count_exp`. Reuse `_period_feature_expr` with `count_exp` stripped and aliases rewritten to window aliases.

- [ ] **Step 4: Verify GREEN**

Run the same pytest command and expect pass.

### Task 5: Official Coverage and Evidence

**Files:**
- Modify: generated reports under `reports/`
- Modify: generated snapshots under `submission_artifacts/`
- Create or update: docs summary if coverage changes materially.

- [ ] **Step 1: Run targeted official tests**

```powershell
python -m pytest tests\test_official_slot.py -q
```

- [ ] **Step 2: Run full pytest**

```powershell
python -m pytest -q
```

- [ ] **Step 3: Refresh official slot coverage**

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports\official_slot_coverage.json --report-output reports\official_slot_coverage.md --sample-size 80 --json
```

- [ ] **Step 4: Run readiness**

```powershell
& "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
```

- [ ] **Step 5: Export submission artifacts**

```powershell
& "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

- [ ] **Step 6: Commit and push**

```powershell
git add src\findsl\official_slot.py tests\test_official_slot.py docs reports submission_artifacts
git commit -m "feat: harden official count expression semantics"
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
$env:ALL_PROXY='socks5://127.0.0.1:7897'
git push origin main
```
