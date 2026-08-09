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

Then-current result after strict `agg_func/count_exp` semantics: `compile_ok = 1411`, `parse_ok = 5792`, `parse_failed = 7`. This number was lower than the earlier 1455 because the compiler no longer treated unsupported aggregate/count semantics as ordinary field filters. Later period, industry, cross-date, and rank-count work raised the grounded compile count to 1532; chained-rank and missing-data audit work raised it to 1536; official alias grounding and string-wildcard fixes later raised the latest grounded compile count to 1607.

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

### Task 7: `count_exp` and `agg_func` Grounding

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`

- [x] **Step 1: Add failing tests for AVG/SUM/MAX/MIN**

Use official-style examples:

```python
def test_compile_official_avg_volume_window():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'AVG', '') > 1000"
    )
    assert "AVG(" in result.sql or "volume_avg_5" in result.sql
```

- [x] **Step 2: Add failing tests for EXIST/CONS**

Use:

```python
def test_compile_official_exist_rise_pct_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨幅', '近5日', '', '', 'EXIST>=3日') > 5%"
    )
    assert "HAVING" in result.sql or "COUNT" in result.sql
```

- [x] **Step 3: Implement minimal window subqueries**

Implemented correlated aggregate subqueries for `AVG/SUM/MAX/MIN`, count subqueries for `EXIST/CONS`, `between` inside count windows, `GROWTH_RISE/GROWTH_FALL` using `MIN_BY/MAX_BY`, and bucketed aggregate counting for `agg_func + count_exp`. Daily growth count windows use `LAG(...) OVER (...)` so "逐日上涨/下跌" is compiled as adjacent trading-day change rather than a fake total-window shortcut.

- [x] **Step 4: Run targeted tests and refresh official coverage**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_slot.py -q
python -m findsl.cli official-slot-coverage --workbook "<official workbook>" --json-output reports\official_slot_coverage.json --report-output reports\official_slot_coverage.md --sample-size 30 --json
```

Evidence at the end of Task 7: `tests\test_official_slot.py` had 30 passing tests. Official coverage was `parse_ok=5792`, `parse_failed=7`, `compile_ok=1411`, `compile_failed=4381`. Remaining `UNSUPPORTED_OFFICIAL_COUNT_EXP` was mostly `rank(..., count_exp)` and count-bearing indicators embedded in arithmetic expressions; those needed a separate rank-over-time design and should not be silently flattened.

### Task 8: Next Required Work - Rank/Then Temporal Semantics

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`

- [x] **Step 1: Design rank-over-time semantics**

Examples remaining in the official workbook include `rank(..., 'CONS=每年') > 10`, `rank(..., 'EXIST>=8') <= 3`, and chained `then rank(...) then rank(...)`. These cannot be reduced to ordinary row filters without changing the meaning. The next design should choose between:

1. bucketed rank counting, where rank is computed per day/week/month/year bucket and the `CONS/EXIST` rule counts buckets;
2. materialized rank feature tables in Doris for high-frequency rank/count combinations;
3. explicit unsupported diagnostics for multi-stage rank chains until Doris evidence confirms the cost model.

- [x] **Step 2: Add failing tests for rank count**

Added representative official-style examples and required the generated SQL to preserve the ordering scope, date bucket, count rule, and outer snapshot constraint.

- [x] **Step 3: Implement only the grounded subset**

Implement rank-over-time only for indicators that already map to official tables. Keep unsupported diagnostics for missing data domains and ambiguous chained-rank semantics.

Implemented the first grounded subset: ordinary numeric/time `rank(..., count_exp)` now computes `ROW_NUMBER()` per `DATE_TRUNC` bucket and counts buckets satisfying the rank predicate. `CONS=每日` requires all effective buckets to satisfy the predicate. `rank(..., count_exp)` with `agg_func` still returns `UNSUPPORTED_OFFICIAL_COUNT_EXP` because that path needs a materialized rank feature table for credible Doris performance.

### Task 9: Official Period, Cross-Date, and Industry Semantics

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`
- Update: `docs/20_官方真实数据适配分析与开发计划.md`

- [x] **Step 1: Add failing tests for period functions**

Covered `record_high/record_low` on official `pxMkTopDays/pxMkBotDays` and `position(...) = '低'` as a grounded CASE expression.

- [x] **Step 2: Implement period function subset**

Price new-high/new-low uses official ext-table days fields. Other mapped numeric/time indicators use legal correlated `MAX/MIN` subqueries. `position` maps current value into `最低/低/中/高/最高` based on period min/max.

- [x] **Step 3: Add failing test for incompatible AND date slots**

Covered `零三年` and `零四年` conditions that previously became impossible global `base.bizdate` constraints.

- [x] **Step 4: Localize conflicting date branches**

When AND branches contain different date constraints, each branch is compiled as a correlated `EXISTS` over the same stock identity instead of forcing all date ranges onto one base row.

- [x] **Step 5: Add and implement grounded `belong_industry`**

Numeric/time indicators can now be compared with industry aggregates keyed by `code.hyBlkRefName`. Missing financial/fund/topic indicators continue to fail with stable unsupported-indicator diagnostics.

- [x] **Step 6: Refresh coverage and tests**

Current evidence after Task 9 and rank-count grounding:

```text
pytest: full suite passed
tests/test_official_slot.py: 36 passed
official workbook: parse_ok=5792, parse_failed=7, compile_ok=1532, compile_failed=4260
UNSUPPORTED_OFFICIAL_COUNT_EXP: 43
UNSUPPORTED_OFFICIAL_FUNCTION: 85
```

### Task 10: Chained Rank and Missing-Data Audit

**Files:**
- Modify: `src/findsl/official_slot.py`
- Test: `tests/test_official_slot.py`
- Update: `README.md`
- Update: `docs/20_官方真实数据适配分析与开发计划.md`
- Create: `docs/21_官方真实数据冲刺计划与验收闭环.md`

- [x] **Step 1: Add failing chained-rank test**

Covered a monotonic official pipeline:

```text
indicator(..., '涨停', '今天') = True
then rank(..., '成交量', 'desc', '今天') <= 50
then rank(..., '主力净流入', 'desc', '今天') <= 10
```

- [x] **Step 2: Implement CTE stage pipeline**

`OfficialSlotCompiler` now flattens top-level `then` chains with more than two stages and emits `stage_0/stage_1/stage_2` CTEs. Each rank stage re-ranks only the previous stage output. Unsupported chained `rank(..., count_exp)` still fails with `UNSUPPORTED_OFFICIAL_COUNT_EXP` instead of generating a heavy ambiguous nested window query.

- [x] **Step 3: Add failing missing-domain classification test**

Covered representative unsupported indicators:

```text
成分股 -> 指数成分与权重数据缺失
归母净利润 -> 财务报表数据缺失
基金十大重仓股 -> 基金产品与持仓数据缺失
我的持仓股 -> 用户账户与自选股数据缺失
龙虎榜净流入 -> 龙虎榜与交易异动数据缺失
相似K线 -> 高级形态/相似度模型数据缺失
```

- [x] **Step 4: Implement coverage-domain audit**

`compile_training_workbook` now returns `compile_error_domains`, and `write_coverage_report` writes a `缺失数据域分层` section. Latest official coverage:

```text
row_count=5799
parse_ok=5792
parse_failed=7
compile_ok=1607
compile_failed=4185
compile_rate_on_all_rows=27.71%
compile_rate_on_parse_ok=27.75%
```

- [x] **Step 5: Refresh official data profile**

Generated local reports:

```text
reports/official_data_profile.md
reports/official_data_profile.json
reports/official_slot_coverage.md
reports/official_slot_coverage.json
```

Official CSV row counts remain:

```text
hsj_stock_code_info: 5686
hsj_stock_hq_basic: 13650347
hsj_stock_hq_ext: 6170822
```

- [x] **Step 6: Update docs**

README, Chapter 20, and Chapter 21 now describe the latest `1607` grounded compile count, chained-rank CTE support, missing-data-domain audit, grounded official aliases, string-wildcard SQL repair, and remaining Doris evidence requirement.

### Task 11: Remaining Required Work

- [ ] **Official Doris evidence on real CSVs**

Load all three official CSVs into Doris, build feature tables, and collect row-count parity, EXPLAIN, latency, and speedup evidence in `reports/official_doris_evidence.md`.

- [ ] **Materialized temporal rank feature table**

Support `rank(..., agg_func, count_exp)` and chained temporal rank with a precomputed Doris feature table. Avoid deeply nested runtime windows.

- [x] **Composite relative date AST**

Support expressions such as `本月的前一周`, `2018年的第五年`, and `最近的第二天` without falling back to `1=1`.

Implemented in `src/findsl/official_time.py` with an internal date interval model. Covered by tests for explicit year ranges (`2006年-12年`, `06年到12年`), `昨天的前1日`, `本月的前一周`, `2012年的后4年`, `一二年的第4年`, `2018年的第五年`, `最近的第二天`, `最近的第二天的后3日`, and the impossible future window `本周的后3日`. That task improved predicate correctness rather than increasing the compile count; later alias and literal repairs raised latest official coverage to `parse_ok=5792`, `parse_failed=7`, `compile_ok=1607`, `compile_failed=4185`.

- [x] **Official real-workbook alias grounding and string wildcard repair**

Implemented in `src/findsl/official_slot.py` and covered by `tests/test_official_slot.py`. Added grounded mappings for `涨停天数/跌停天数/连续涨停天数`, `沪港通标识/深港通标识`, `委比`, `买方未匹配量/卖方未匹配量`, and MA period aliases `一周均线/一个月均线/一个季度均线`. Fixed string literals such as `%科技%` so they compile to `LIKE '%科技%'` while numeric percent literals such as `5%` still compile to numeric `5`. Latest official workbook coverage is `compile_ok=1607`, `compile_failed=4185`.

- [ ] **Second-pass missing-data-domain classification**

Reduce the large `官方三表未覆盖的其他指标` bucket by adding more precise categories for ownership ratio, market-cap style labels, chip indicators, and company-action metadata.
