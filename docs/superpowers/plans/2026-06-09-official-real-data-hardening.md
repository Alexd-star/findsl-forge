# Official Real Data Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the official Topic 19 real-data adapter from parse-and-basic-compile into a truthful, high-scoring Doris evidence path.

**Architecture:** Keep the original internal DSL compiler unchanged and harden the official slot DSL adapter as a separate front end. Official slot SQL must be grounded only in the three provided official A-share tables plus deterministic feature tables derived from those tables.

**Tech Stack:** Python 3.9, pytest, pandas/openpyxl for workbook profiling, Apache Doris SQL assets, PowerShell runbooks, official CSV files under the Topic 19 package.

---

### Task 1: Official Date Normalization

**Files:**
- Create: `src/findsl/official_time.py`
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_time.py`
- Test: `tests/test_official_slot.py`

- [x] **Step 1: Write failing tests**

```python
def test_normalize_current_day_aliases_to_official_anchor_date():
    for text in ["今天", "今日", "当前", "目前", "当日", "当天", "本日"]:
        result = normalize_official_date(text, anchor_date="2026-04-14")
        assert result.constraints == ["base.bizdate = '2026-04-14'"]
        assert result.warnings == []
```

- [x] **Step 2: Verify red**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_time.py -q
```

Expected initial result: import failure for `findsl.official_time`.

- [x] **Step 3: Implement normalizer**

Implemented deterministic handling for empty dates, current-day aliases, previous trading day, recent N days, this week/month/year, previous year, Chinese two-digit years, Arabic years, ISO dates, and month-day dates.

- [x] **Step 4: Integrate compiler**

`OfficialSlotCompiler(anchor_date="2026-04-14", trading_dates=[...])` now sends every date slot through `normalize_official_date`.

- [x] **Step 5: Verify green**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_time.py tests\test_official_slot.py -q
```

Expected current result: pass.

### Task 2: Official Numeric Unit Normalization

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`

- [x] **Step 1: Write failing tests**

```python
def test_compile_official_numeric_scales_to_human_units():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '市净率', '今日', '', '', '') < 2 "
        "and indicator('', '', '涨幅', '今日', '', '', '') > 5%"
    )
    assert "(base.pBR / 10000.0) < 2" in result.sql
    assert "((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0)) > 5" in result.sql
```

- [x] **Step 2: Verify red**

Expected initial failure: raw `base.pBR < 2` and raw fraction-based rise expression.

- [x] **Step 3: Implement scale-aware expressions**

Price fields use `/ 10000.0`; percentage, ratio and valuation fields use `/ 10000.0`; rise/fall percentage expressions multiply by `100.0`; market value uses scaled price times share count.

- [x] **Step 4: Verify green**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_slot.py -q
```

Expected current result: pass.

### Task 3: Derived Technical Feature Layer

**Files:**
- Modify: `src/findsl/official_slot.py`
- Modify: `deploy/doris/official/04_feature_tables.sql`
- Modify: `tests/test_official_doris_assets.py`
- Test: `tests/test_official_slot.py`

- [x] **Step 1: Write failing tests**

```python
def test_compile_official_technical_indicators_from_feature_table():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '5日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '放量', '今天', '', '', '') = True"
    )
    assert "newzl.hsj_stock_hq_basic_technical AS tech" in result.sql
    assert "tech.ma5 > 10" in result.sql
    assert "tech.volume_breakout = TRUE" in result.sql
```

- [x] **Step 2: Verify red**

Expected initial failure: unsupported indicator `5日均线`.

- [x] **Step 3: Add technical mappings**

Mapped `5日均线/10日均线/20日均线/60日均线/阳线/阴线/十字星/放量/均线多头排列/均线空头排列/上涨趋势` to `hsj_stock_hq_basic_technical`.

- [x] **Step 4: Add Doris feature table**

`04_feature_tables.sql` now creates and rebuilds `newzl.hsj_stock_hq_basic_technical` with scaled prices, MA windows, volume averages, candlestick flags, volume-breakout flag, trend flags, and pressure/support crossing flags.

- [x] **Step 5: Verify green**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_slot.py tests\test_official_doris_assets.py -q
```

Expected current result: pass.

### Task 4: OR Branch Constraint Isolation

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`

- [x] **Step 1: Write failing test**

```python
def test_compile_or_keeps_branch_specific_date_constraints_inside_each_branch():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('创业板', '', '开盘价', '20年', '', '', '') > 50 "
        "or indicator('创业板', '', '开盘价', '近三年', '', '', '') ~= 92"
    )
    assert "OR" in result.sql
    assert "base.bizdate BETWEEN '2020-01-01' AND '2020-12-31' AND base.bizdate BETWEEN '2024-01-01' AND '2026-04-14'" not in result.sql
```

- [x] **Step 2: Verify red**

Expected initial failure: both date ranges lifted into the global `WHERE`.

- [x] **Step 3: Implement branch-local constraints**

For `OR`, each branch now renders `condition AND branch_constraints` before joining the two branches. `AND` still combines constraints normally.

- [x] **Step 4: Verify green**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_slot.py::test_compile_or_keeps_branch_specific_date_constraints_inside_each_branch -q
```

Expected current result: pass.

### Task 5: Refresh Official Coverage and Documentation

**Files:**
- Modify: `docs/20_官方真实数据适配分析与开发计划.md`
- Generated locally: `reports/official_slot_coverage.json`
- Generated locally: `reports/official_slot_coverage.md`

- [x] **Step 1: Regenerate coverage**

Run:

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage `
  --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" `
  --json-output reports\official_slot_coverage.json `
  --report-output reports\official_slot_coverage.md `
  --sample-size 30 `
  --json
```

Expected current result: `compile_ok = 1455`, `parse_ok = 5792`, `parse_failed = 7`.

- [x] **Step 2: Update human-readable plan**

`docs/20_官方真实数据适配分析与开发计划.md` now records the root causes, current coverage, completed fixes, and remaining P0/P1 work.

### Task 6: Next Required Work - Official Doris Evidence

**Files:**
- Use: `deploy/doris/official/01_schema.sql`
- Use: `deploy/doris/official/02_stream_load.md`
- Use: `deploy/doris/official/03_smoke_queries.sql`
- Use: `deploy/doris/official/04_feature_tables.sql`
- Create after execution: `reports/official_doris_evidence.md`

- [ ] **Step 1: Start Doris and create schema**

Run the SQL in `deploy/doris/official/01_schema.sql` against the local Doris FE MySQL port.

Expected: database `newzl` and three official base tables exist.

- [ ] **Step 2: Stream Load official CSV files**

Follow `deploy/doris/official/02_stream_load.md` for `hsj_stock_code_info.csv`, `hsj_stock_hq_basic.csv`, and `hsj_stock_hq_ext.csv`.

Expected row counts:

```text
hsj_stock_code_info: 5686
hsj_stock_hq_basic: 13650347
hsj_stock_hq_ext: 6170822
```

- [ ] **Step 3: Build feature tables**

Run `deploy/doris/official/04_feature_tables.sql`.

Expected: prefix tables and `hsj_stock_hq_basic_technical` are populated.

- [ ] **Step 4: Collect official benchmark evidence**

Run representative compiled SQL for simple filters, rank queries, technical-feature filters, and prefix-table queries. Capture `EXPLAIN`, row counts, repeated latency, and speedup into `reports/official_doris_evidence.md`.

Expected: at least 10 official compiled SQL cases execute successfully on official data; feature-table queries should avoid query-time MA windows.

### Task 7: Next Required Work - `count_exp` and `agg_func`

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`

- [ ] **Step 1: Add failing tests for AVG/SUM/MAX/MIN**

Use official-style examples:

```python
def test_compile_official_avg_volume_window():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'AVG', '') > 1000"
    )
    assert "AVG(" in result.sql or "volume_avg_5" in result.sql
```

- [ ] **Step 2: Add failing tests for EXIST/CONS**

Use:

```python
def test_compile_official_exist_rise_pct_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨幅', '近5日', '', '', 'EXIST>=3日') > 5%"
    )
    assert "HAVING" in result.sql or "COUNT" in result.sql
```

- [ ] **Step 3: Implement minimal window subqueries**

Start with `成交量、成交额、涨幅、主力净流入`; use table-specific expressions already normalized by `INDICATORS`.

- [ ] **Step 4: Run targeted and full tests**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_slot.py -q
python -m pytest -q
```

Expected: all tests pass and official coverage increases without hiding unsupported missing data.
