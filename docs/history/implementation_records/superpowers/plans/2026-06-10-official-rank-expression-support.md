# Official Rank Expression Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持官方 DSL 中 `rank(...)` 作为算术表达式的一部分，例如 `rank(...)+rank(...) > 0`、`rank(...)/rank(...) <= 10` 和 `rank(...) ~= 10`。

**Architecture:** 保留现有顶层 `rank(...) <= N` 和 `then rank(...) <= N` 的高效编译路径；仅当 `rank(...)` 出现在普通表达式中时，把它编译为“当前 `base` 标的在对应排名集合中的 `rank_no`”标量子查询。这样新增能力不会改变旧的排名筛选 SQL 形态。

**Tech Stack:** Python 3.11+, pytest, Apache Doris SQL window function `ROW_NUMBER()`, official three-table adapter.

---

### Task 1: Add Failing Rank Expression Tests

**Files:**
- Modify: `tests/test_official_slot.py`

- [ ] **Step 1: Write tests**

```python
def test_rank_function_can_be_used_inside_arithmetic_expression():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '涨停天数', 'desc', '本周', '', '', '') "
        "+ rank('', '', '跌停天数', 'desc', '本周', '', '', '') > 0"
    )

    assert "SELECT ranked.rank_no" in result.sql
    assert "ROW_NUMBER() OVER" in result.sql
    assert "ORDER BY rb.upCount DESC" in result.sql
    assert "ORDER BY rb.downCount DESC" in result.sql
    assert "ranked.mktcode = base.mktcode" in result.sql


def test_rank_expression_supports_division_with_ext_indicators():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '主力净流入', 'desc', '今天', '', '', '') "
        "/ rank('', '', '主力净流出', 'desc', '今天', '', '', '') <= 3"
    )

    assert "ORDER BY rext.ZJLXMainNetTur DESC" in result.sql
    assert "ORDER BY (-rext.ZJLXMainNetTur) DESC" in result.sql
    assert "newzl.hsj_stock_hq_ext AS rext" in result.sql


def test_rank_approximate_operator_falls_back_to_scalar_rank_expression():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '跌幅', 'desc', '四月二十号', '', 'AVG', '') ~= 10"
    )

    assert "SELECT ranked.rank_no" in result.sql
    assert "= 10" in result.sql
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests\test_official_slot.py::test_rank_function_can_be_used_inside_arithmetic_expression tests\test_official_slot.py::test_rank_expression_supports_division_with_ext_indicators tests\test_official_slot.py::test_rank_approximate_operator_falls_back_to_scalar_rank_expression -q
```

Expected: all three fail before implementation. The first two fail with `UNSUPPORTED_OFFICIAL_FUNCTION: rank`; the third fails with `OFFICIAL_RANK_OPERATOR_ERROR`.

### Task 2: Implement Scalar Rank Expression

**Files:**
- Modify: `src/findsl/official_slot.py`

- [ ] **Step 1: Add rank branch to `_expr_sql()`**

Inside the `OfficialFunctionCall` branch:

```python
if name == "rank":
    return self._rank_scalar_expr(node, warnings)
```

- [ ] **Step 2: Add `_rank_scalar_expr()`**

Compile rank into a scalar subquery tied to the current outer `base` row:

```python
def _rank_scalar_expr(self, rank_call: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
    if self._rank_count_exp(rank_call):
        raise OfficialSlotError(
            "UNSUPPORTED_OFFICIAL_COUNT_EXP",
            "rank(...) inside arithmetic expressions does not yet support count_exp",
        )
    rank_expr = self._rank_expr_without_count_exp(rank_call, warnings)
    rank_sql = _rank_alias_sql(rank_expr.sql)
    constraints = [_rank_alias_sql(item) for item in rank_expr.constraints]
    tables = self._ordered_tables(rank_expr.tables)
    joins = self._joins_for_aliases(tables, "rb", "rcode", "rext")
    where = " AND ".join(_dedupe(constraints)) or "1=1"
    sql = (
        "(SELECT ranked.rank_no\n"
        " FROM (\n"
        "   SELECT rb.mktcode, rb.tgtcode, rb.bizdate,\n"
        f"          ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no\n"
        "   FROM newzl.hsj_stock_hq_basic AS rb\n"
        f"{joins}"
        f"   WHERE {where}\n"
        " ) AS ranked\n"
        " WHERE ranked.mktcode = base.mktcode\n"
        "   AND ranked.tgtcode = base.tgtcode\n"
        "   AND ranked.bizdate = base.bizdate)"
    )
    return SqlExpr(sql, "numeric", tables, [])
```

- [ ] **Step 3: Let unsupported direct rank operators use scalar fallback**

Keep current optimized `_rank_condition_sql()` only for `<=`, `=`, `<`, `>`, `>=`, `!=`. Let `rank(...) ~= 10` and `rank(...) between ...` flow into `_comparison_sql()` so `_expr_sql()` can compile them through `_rank_scalar_expr()`.

### Task 3: Verify And Refresh Coverage

**Files:**
- Test: `tests/test_official_slot.py`
- Generated reports: `reports/official_slot_coverage.json`, `reports/official_slot_coverage.md`

- [ ] **Step 1: Run target tests**

Run:

```powershell
python -m pytest tests\test_official_slot.py -q
```

Expected: official slot tests pass.

- [ ] **Step 2: Refresh official coverage**

Run:

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports\official_slot_coverage.json --report-output reports\official_slot_coverage.md --sample-size 50 --json
```

Expected: `UNSUPPORTED_OFFICIAL_FUNCTION: rank` drops below 31. Some rows will still fail if the ranked indicators are not present in the official three-table dataset.

### Self-Review Notes

- This plan does not support `rank(..., count_exp)` inside arithmetic expressions. That requires a temporal rank feature table and is tracked as a later task.
- This plan does not fabricate missing financial or fund indicators. If `rank('归母净利润')` is used inside arithmetic, it should still fail with `UNSUPPORTED_OFFICIAL_INDICATOR`.
- Existing top-level rank SQL should remain unchanged for normal `rank(...) <= N` filters.
