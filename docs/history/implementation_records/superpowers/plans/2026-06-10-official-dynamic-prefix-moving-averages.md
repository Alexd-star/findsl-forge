# Official Dynamic Prefix Moving Averages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让官方真实 DSL 中的动态 `N日均线` 与 `N日均量线` 在普通筛选、排名、上穿下穿、粘合、回调、聚合和出现次数语义中可落地编译为 Doris SQL。

**Architecture:** 在 `src/findsl/official_slot.py` 中新增统一的指标解析入口，把固定指标字典和动态前缀派生指标合并为同一个 `IndicatorMeta` 解析结果。动态均线不扩展技术特征表列，而是使用 `newzl.hsj_stock_hq_basic_prefix` 的前缀和字段生成别名可重写的标量子查询，避免为官方样例里的 7、11、13、45、754、850 等窗口逐一建列。

**Tech Stack:** Python 3.11+, pytest, pandas/openpyxl, Apache Doris SQL, official CSV package, `hsj_stock_hq_basic_prefix` feature table.

---

### Task 1: Add Failing Tests For Dynamic Prefix Indicators

**Files:**
- Modify: `tests/test_official_slot.py`

- [ ] **Step 1: Write the failing tests**

Add tests that express the desired public behavior:

```python
def test_compile_dynamic_daily_ma_uses_official_prefix_table():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '7日均线', '今天', '', '', '') > 10"
    )

    assert "newzl.hsj_stock_hq_basic_prefix AS p" in result.sql
    assert "p_prev.row_no = p.row_no - 7" in result.sql
    assert "p.close_prefix" in result.sql
    assert "p.close_count_prefix" in result.sql
    assert "/ 10000.0" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "hsj_stock_hq_basic_prefix" in result.requires_tables


def test_compile_dynamic_daily_volume_average_uses_official_prefix_table():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '8日均量线', '今天', '', '', '') > 1000"
    )

    assert "newzl.hsj_stock_hq_basic_prefix AS p" in result.sql
    assert "p_prev.row_no = p.row_no - 8" in result.sql
    assert "p.volume_prefix" in result.sql
    assert "p.volume_count_prefix" in result.sql
    assert "hsj_stock_hq_basic_prefix" in result.requires_tables


def test_dynamic_prefix_indicators_work_inside_pattern_and_cross_functions():
    reset_result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "reset('', '', '最新价', '25日均线', '今天', '', '') = True"
    )
    cross_result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "cross_above('', '', '13日均线', '55日均线', '今天', '', '') = True"
    )

    assert "p_prev.row_no = p.row_no - 25" in reset_result.sql
    assert "p_prev.row_no = p.row_no - 13" in cross_result.sql
    assert "p_prev.row_no = p.row_no - 55" in cross_result.sql
    assert "hsj_stock_hq_basic_prefix" in reset_result.requires_tables
    assert "hsj_stock_hq_basic_prefix" in cross_result.requires_tables


def test_weekly_and_monthly_moving_averages_remain_explicitly_unsupported():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile("indicator('', '', '5周均线', '', '', '', '') > 0")

    assert excinfo.value.code == "UNSUPPORTED_OFFICIAL_INDICATOR"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests\test_official_slot.py::test_compile_dynamic_daily_ma_uses_official_prefix_table tests\test_official_slot.py::test_compile_dynamic_daily_volume_average_uses_official_prefix_table tests\test_official_slot.py::test_dynamic_prefix_indicators_work_inside_pattern_and_cross_functions tests\test_official_slot.py::test_weekly_and_monthly_moving_averages_remain_explicitly_unsupported -q
```

Expected: first three tests fail with `UNSUPPORTED_OFFICIAL_INDICATOR`; weekly/monthly unsupported test passes.

### Task 2: Implement Dynamic Indicator Resolution

**Files:**
- Modify: `src/findsl/official_slot.py`

- [ ] **Step 1: Add a resolver helper**

Add helpers after the static `INDICATORS` mapping:

```python
def _resolve_indicator_meta(indicator_name: str) -> Optional[IndicatorMeta]:
    meta = INDICATORS.get(indicator_name)
    if meta:
        return meta
    return _dynamic_prefix_indicator_meta(indicator_name)
```

- [ ] **Step 2: Add prefix SQL builders**

Add a dynamic parser that accepts `N日均线`/`N天均线` and `N日均量线`/`N天均量线`, where `N` can be Arabic or small Chinese numerals:

```python
def _dynamic_prefix_indicator_meta(indicator_name: str) -> Optional[IndicatorMeta]:
    match = re.fullmatch(r"(?P<count>\d+|[零〇一二两三四五六七八九十百两]+)(?:日|天)均(?P<volume>量)?线", indicator_name)
    if not match:
        return None
    window = _parse_small_count(match.group("count"))
    if window <= 0:
        return None
    if match.group("volume"):
        expression = _dynamic_prefix_average_expr(window, "volume_prefix", "volume_count_prefix", scale_divisor=None)
    else:
        expression = _dynamic_prefix_average_expr(window, "close_prefix", "close_count_prefix", scale_divisor=10000.0)
    return IndicatorMeta("hsj_stock_hq_basic_prefix", kind="numeric", expression=expression)
```

- [ ] **Step 3: Ensure alias rewriting works**

The expression must be written against `base.` so existing `_rewrite_aliases()` can rewrite it for `wb/rb/lb` aliases:

```python
def _dynamic_prefix_average_expr(window: int, prefix_column: str, count_column: str, scale_divisor: Optional[float]) -> str:
    avg = (
        "(SELECT ((p.{prefix} - COALESCE(p_prev.{prefix}, 0)) * 1.0 "
        "/ NULLIF(p.{count_col} - COALESCE(p_prev.{count_col}, 0), 0))\n"
        " FROM newzl.hsj_stock_hq_basic_prefix AS p\n"
        " LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p_prev "
        "ON p_prev.mktcode = p.mktcode "
        "AND p_prev.tgtcode = p.tgtcode "
        "AND p_prev.row_no = p.row_no - {window}\n"
        " WHERE p.mktcode = base.mktcode "
        "AND p.tgtcode = base.tgtcode "
        "AND p.bizdate = base.bizdate)"
    ).format(prefix=prefix_column, count_col=count_column, window=window)
    if scale_divisor is None:
        return avg
    return f"({avg} / {scale_divisor:.1f})"
```

- [ ] **Step 4: Replace direct dictionary lookups**

Replace direct `INDICATORS.get(indicator_name)` calls used for compile-time indicator lookup with `_resolve_indicator_meta(indicator_name)` in:

- `_technical_pattern_operand_sql`
- `_indicator_expr`
- `_count_exp_comparison_sql`
- `_belong_industry_expr`
- `_record_extreme_expr`
- `_position_expr`

- [ ] **Step 5: Preserve requires_tables metadata**

Update `_ordered_tables()` to keep `hsj_stock_hq_basic_prefix` in `requires_tables`, while `_joins()`, `_window_joins()` and `_joins_for_aliases()` continue not to join it because the scalar subquery references it directly.

### Task 3: Verify Dynamic Indicator Support

**Files:**
- Test: `tests/test_official_slot.py`
- Generated reports: `reports/official_slot_coverage.json`, `reports/official_slot_coverage.md`

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m pytest tests\test_official_slot.py -q
```

Expected: all official slot tests pass.

- [ ] **Step 2: Run full regression tests**

Run:

```powershell
python -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Refresh official coverage**

Run:

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports\official_slot_coverage.json --report-output reports\official_slot_coverage.md --sample-size 50 --json
```

Expected: `compile_ok` increases above `1718`, and dynamic daily MA names disappear from unsupported indicator details unless another unsupported field in the same row becomes the next root cause.

### Task 4: Refresh Evidence And Commit

**Files:**
- Modify generated evidence under `submission_artifacts/`
- Modify generated coverage reports under `reports/`

- [ ] **Step 1: Run readiness gate**

Run:

```powershell
& "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
```

Expected: blocking gates pass; warning count remains controlled and explained.

- [ ] **Step 2: Export submission artifacts**

Run:

```powershell
& "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

Expected: `submission_artifacts/evidence_summary.md` reflects the new official coverage and current Git metadata.

- [ ] **Step 3: Commit and push**

Run:

```powershell
git add src/findsl/official_slot.py tests/test_official_slot.py reports/official_slot_coverage.json reports/official_slot_coverage.md docs/24_官方真实数据第三轮解剖与动态前缀均线补强计划.md docs/superpowers/plans/2026-06-10-official-dynamic-prefix-moving-averages.md submission_artifacts
git commit -m "feat: support official dynamic prefix moving averages"
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
$env:ALL_PROXY='socks5://127.0.0.1:7897'
git push origin main
```

Expected: push succeeds on `main`.

### Self-Review Notes

- This plan intentionally does not support `5周均线` or `1月均线`, because the official package only provides daily rows and does not provide weekly/monthly resampled K-line fields. Treating weekly/monthly as daily windows would be a semantic error.
- This plan intentionally does not fabricate missing financial, fund, component, user holding, or concept popularity fields. Those gaps should remain in the coverage report as unavailable data domains.
- Dynamic prefix indicators are grounded in `close_prefix/close_count_prefix` and `volume_prefix/volume_count_prefix`, matching the existing fixed-window feature table logic.
