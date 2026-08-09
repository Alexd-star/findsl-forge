# Official Technical Pattern Functions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在官方真实数据边界内补齐 `reset` 与 `close_together` 的可解释、可配置 Doris SQL 编译能力，降低官方 workbook 中 `UNSUPPORTED_OFFICIAL_FUNCTION` 缺口。

**Architecture:** 继续保持“无字段不伪造”的编译原则。`reset/close_together` 只对官方三表或 `hsj_stock_hq_basic_technical` 已派生出的价格、均线、均量、支撑位、压力位等指标落地；K/D/J、DIF、EXPMA、单位净值、财务/基金/指数/用户域仍返回缺失指标诊断。阈值放入 `configs/official_technical_patterns.json`，编译器读取配置生成相对价差 SQL。

**Tech Stack:** Python 3.9+、pytest、Apache Doris SQL、官方 `选股提槽实例.xlsx`、`src/findsl/official_slot.py`、`configs/*.json`。

---

## 1. 当前真实数据和完成度判断

官方当前阶段只提供三张可执行行情表：`hsj_stock_code_info`、`hsj_stock_hq_basic`、`hsj_stock_hq_ext`，以及由本项目确定性构建出的 `hsj_stock_hq_basic_prefix`、`hsj_stock_hq_ext_prefix`、`hsj_stock_hq_basic_technical`。真实 Doris evidence 已经证明基础表和三张派生特征表行数闭环，官方 workbook 覆盖率为 `row_count=5799`、`parse_ok=5792`、`compile_ok=1682`。

未编译的 4110 条样例里，最大根因仍是数据域缺失。财务报表、基金产品和持仓、指数成分、主营业务、题材热度、龙虎榜、用户持仓等不在官方三表里，不能靠编译器凭空变出字段。真正属于当前代码还能补齐的，是 `UNSUPPORTED_OFFICIAL_FUNCTION` 中的技术形态函数，其中 `reset` 出现 29 次、`close_together` 出现 27 次。它们直接对应官方样例中的“回踩均线”“回调到支撑/压力位”“均线粘合”“沿着 5 日线运行”等表达，且多数可以用已有技术特征表表达。

外部技术分析资料的共识是：移动平均线用于平滑价格并识别趋势，短周期和长周期均线的关系常用于趋势判断；回调通常指上涨趋势中的短期回落，技术分析会观察价格是否回落到移动平均线、支撑位等关键位置附近。参考资料包括 Investopedia 的 Moving Average 说明、Pullback 说明，以及 Fidelity 的 SMA 说明。这里不把这些资料当作投资建议，只用来解释为什么用“相对距离阈值”来刻画“附近”“粘合”更合理。

## 2. 实现边界

`close_together(a, b)` 的落地子集：

- 当左指标为空时，用 `最新价` 作为默认左指标，符合“股价沿着/粘合某均线”的自然语言。
- 当左右指标都能映射到官方三表或技术特征表，并且类型为 numeric/time 时，生成 `ABS(left-right)/NULLIF(max(abs(left),abs(right)),0) <= threshold`。
- 当右指标为空但左指标是均线时，不强行推断多均线组合；官方样例多数是左空、右均线或两个明确均线。
- 带 `count_exp` 的样例先支持窗口内出现次数/连续次数的“计数阈值”版本，沿用现有 `CONS` 警告口径；真正最长连续段检测后续进入专用 feature table。

`reset(a, b)` 的落地子集：

- 当左指标为空时，用 `最新价` 作为默认左指标，符合“股价回踩均线/支撑位/压力位”的官方语料。
- 当左右指标能映射到三表或技术特征表且为 numeric/time 时，生成“接近目标线且不明显跌破”的表达：`ABS(left-right)/NULLIF(abs(right),0) <= threshold`，并允许 `left >= right * (1 - below_tolerance)`。
- 该实现不声称识别完整趋势周期，只解决官方 DSL 中“回踩到某线附近”的可执行子语义；趋势前置条件由 DSL 里已有 `涨幅/均线向上/record_high/多头排列` 等条件表达。
- 带 `count_exp` 的样例同样走窗口计数版本。

阈值默认值：

- `close_together_relative_threshold = 0.03`：左右指标相对距离 3% 以内视为粘合。
- `reset_near_line_threshold = 0.02`：当前值距离目标线 2% 以内视为回踩到附近。
- `reset_below_line_tolerance = 0.005`：允许轻微低于目标线 0.5%，避免真实行情中一分钱级别噪声导致误判。

这些阈值不是硬编码在函数里，而是放在配置文件中，答辩时可以解释为“默认工程阈值，可按券商业务口径调整”。

## 3. 文件结构

- Create: `configs/official_technical_patterns.json`
  - 存放 `reset`、`close_together` 默认阈值、说明、版本。
- Modify: `src/findsl/official_slot.py`
  - 新增配置加载。
  - 新增 `_technical_pattern_expr()`、`_close_together_expr()`、`_reset_expr()`、`_pattern_count_exp_comparison_sql()`。
  - 在 `_expr_sql()` 和 `_comparison_sql()` 中接入官方函数。
- Modify: `tests/test_official_slot.py`
  - 增加 `close_together/reset` 成功、取反、count_exp、缺失指标诊断测试。
- Create: `docs/23_官方真实数据二次解剖与技术形态函数补强.md`
  - 中文记录真实数据二次分析、官方样例解读、实现边界、验证命令、后续风险。

## 4. TDD 任务

### Task 1: close_together 普通比较

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify later: `src/findsl/official_slot.py`

- [ ] **Step 1: Write the failing test**

```python
def test_compile_close_together_default_price_to_ma_uses_configured_relative_threshold():
    result = OfficialSlotCompiler().compile(
        "close_together('', '', '', '20日均线', '今天', '', '') = True"
    )

    assert "ABS((base.lastPx / 10000.0) - tech.ma20)" in result.sql
    assert "0.03" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "hsj_stock_hq_basic_technical" in result.requires_tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\test_official_slot.py::test_compile_close_together_default_price_to_ma_uses_configured_relative_threshold -q`

Expected: FAIL with `UNSUPPORTED_OFFICIAL_FUNCTION: close_together`.

- [ ] **Step 3: Implement minimal compiler support**

Add `close_together` to `_expr_sql()` and generate relative distance SQL for numeric indicators.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\test_official_slot.py::test_compile_close_together_default_price_to_ma_uses_configured_relative_threshold -q`

Expected: PASS.

### Task 2: reset 普通比较与 False 取反

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify later: `src/findsl/official_slot.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_compile_reset_default_price_to_support_line_uses_near_line_threshold():
    result = OfficialSlotCompiler().compile(
        "reset('', '', '', '支撑位', '今天', '', '') = True"
    )

    assert "ABS((base.lastPx / 10000.0) - (base.support / 10000.0))" in result.sql
    assert "0.02" in result.sql
    assert "0.005" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_reset_false_negates_grounded_pattern_expression():
    result = OfficialSlotCompiler().compile(
        "reset('', '', '最新价', '10日均线', '今天', '', '') = False"
    )

    assert "NOT (" in result.sql
    assert "tech.ma10" in result.sql
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests\test_official_slot.py::test_compile_reset_default_price_to_support_line_uses_near_line_threshold tests\test_official_slot.py::test_compile_reset_false_negates_grounded_pattern_expression -q`

Expected: FAIL with `UNSUPPORTED_OFFICIAL_FUNCTION: reset`.

- [ ] **Step 3: Implement minimal compiler support**

Add `reset` to `_expr_sql()` and generate near-line SQL. Keep missing indicators as `UNSUPPORTED_OFFICIAL_INDICATOR`.

- [ ] **Step 4: Run tests to verify they pass**

Run: same command.

Expected: PASS.

### Task 3: count_exp for pattern functions

**Files:**
- Modify: `tests/test_official_slot.py`
- Modify later: `src/findsl/official_slot.py`

- [ ] **Step 1: Write failing tests**

```python
def test_compile_close_together_count_exp_uses_window_count():
    result = OfficialSlotCompiler(
        trading_dates=["2026-04-08", "2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"]
    ).compile("close_together('', '', '', '5日均线', '近5日', '', 'CONS=5日') = True")

    assert "SELECT COUNT(*)" in result.sql
    assert "SUM(CASE WHEN" in result.sql
    assert "ABS((wb.lastPx / 10000.0) - wt.ma5)" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\test_official_slot.py::test_compile_close_together_count_exp_uses_window_count -q`

Expected: FAIL with unsupported function or count expression path.

- [ ] **Step 3: Implement count_exp comparison path**

In `_comparison_sql()`, if left is `reset/close_together` and arg 6 has `count_exp`, route to a pattern count helper. It should rewrite aliases to `wb/wc/we/wt`, use `_window_correlated_where()`, join required tables, and apply `_parse_count_exp_rule()`.

- [ ] **Step 4: Run test to verify it passes**

Run: same command.

Expected: PASS.

### Task 4: Missing data remains honest

**Files:**
- Modify: `tests/test_official_slot.py`

- [ ] **Step 1: Write failing-or-existing test**

```python
def test_close_together_missing_indicator_stays_diagnostic_not_fake_sql():
    with pytest.raises(OfficialSlotError) as exc:
        OfficialSlotCompiler().compile(
            "close_together('', '', 'K值', 'D值', '近五天', '', '') = True"
        )

    assert exc.value.code == "UNSUPPORTED_OFFICIAL_INDICATOR"
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests\test_official_slot.py::test_close_together_missing_indicator_stays_diagnostic_not_fake_sql -q`

Expected: PASS after helper reuses `INDICATORS` lookup.

### Task 5: Coverage and evidence refresh

**Files:**
- Modify generated: `reports/official_slot_coverage.md`
- Modify generated: `reports/official_slot_coverage.json`
- Modify generated/exported: `submission_artifacts/evidence_snapshots/*`
- Modify generated/exported: `submission_artifacts/evidence_summary.md`

- [ ] **Step 1: Run targeted tests**

Run: `python -m pytest tests\test_official_slot.py -q`

Expected: all tests in file pass.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Refresh official coverage**

Run:

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage `
  --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" `
  --json-output reports\official_slot_coverage.json `
  --report-output reports\official_slot_coverage.md `
  --sample-size 50 `
  --json
```

Expected: `UNSUPPORTED_OFFICIAL_FUNCTION: reset` and `UNSUPPORTED_OFFICIAL_FUNCTION: close_together` drop or disappear for data-grounded cases. Compile count should increase unless newly reached samples then fail honestly on missing indicators/select types.

- [ ] **Step 4: Export submission artifacts**

Run: `pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1`

Expected: official coverage snapshots and evidence summary refreshed.

- [ ] **Step 5: Readiness**

Run: `pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1`

Expected: blocking gates pass. If warning count is only dirty Git state, commit before final readiness snapshot.

## 5. Spec coverage self-review

本计划直接覆盖赛题“全量领域函数与复合逻辑”“声明式业务规则”“Doris SQL 自动化编译”的下一块缺口。它不会解决财务、基金、指数、用户域缺失，因为当前官方真实数据没有这些表；这些继续由覆盖率报告和缺失数据域诊断解释。计划不包含占位步骤，所有命令和预期结果均可复现。

