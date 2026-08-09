# 官方真实数据二次补强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于官方真实 workbook 和三张 Doris A 股 CSV，继续补齐可由官方字段严谨支撑的槽位映射、技术特征表和验收报告，同时保留缺失数据域的稳定诊断。

**Architecture:** 本轮不重写官方槽位编译器，而是在 `official_slot.py` 的指标注册表和 `deploy/doris/official/04_feature_tables.sql` 的技术特征层上做小步增强。所有新增能力必须先有单元测试约束，再修改实现；无法由三张官方表支撑的财务、基金、指数成分、用户持仓、题材热度等继续保持 `UNSUPPORTED_OFFICIAL_INDICATOR`，不生成伪 SQL。

**Tech Stack:** Python official DSL parser/compiler, pytest, Apache Doris SQL assets, official CSV/workbook coverage reports.

---

## Context Map

本轮重新读取了官方资料目录：

- `选股 DSL 规范文档/选股提槽实例.xlsx`：5799 条官方训练样例，5792 条可解析，7 条语料本身存在引号、括号或残缺 `and` 问题。
- `Doris A股行情数据集/hsj_stock_code_info.csv`：5686 行，17 列，支撑市场、名称、行业和通联标志。
- `Doris A股行情数据集/hsj_stock_hq_basic.csv`：约 1365 万行，56 列，支撑价格、成交、估值、涨跌停、压力支撑和盘口委托字段。
- `Doris A股行情数据集/hsj_stock_hq_ext.csv`：约 617 万行，64 列，支撑集合竞价、主力资金、大小单、创新高低、破板、最大回撤等衍生字段。

最新官方覆盖率基线为：

```text
row_count=5799
parse_ok=5792
parse_failed=7
compile_ok=1607
compile_failed=4185
compile_rate_on_all_rows=27.71%
compile_rate_on_parse_ok=27.75%
```

剩余失败最多的是 `成分股`、`跟踪指数`、`热门`、`主营业务`、`基金类型`、`归母净利润`、`上市日期`、`龙头股`、`股息率` 等。它们多数不在本批三张官方行情表中，不能通过硬编码解决。本轮只处理官方三表或技术特征表能够证明的数据。

## Task 1: Long-Window Technical Feature Columns

**Files:**
- Modify: `deploy/doris/official/04_feature_tables.sql`
- Modify: `tests/test_official_doris_assets.py`

- [x] **Step 1: Write failing asset assertions**

Add assertions requiring the official technical table to expose:

```text
ma3, ma30, ma120, ma200, ma250
volume_avg_10, volume_avg_30, volume_avg_60
```

Expected first run: pytest fails because those columns are not present.

- [x] **Step 2: Add Doris feature columns**

Extend `hsj_stock_hq_basic_technical` with those columns, include them in the `INSERT` projection, and compute them with Doris window `AVG(...) OVER (PARTITION BY mktcode,tgtcode ORDER BY bizdate ROWS BETWEEN N-1 PRECEDING AND CURRENT ROW)`.

- [x] **Step 3: Re-run asset tests**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_doris_assets.py -q
```

Expected: all official Doris asset tests pass.

## Task 2: Grounded Alias Expansion

**Files:**
- Modify: `src/findsl/official_slot.py`
- Modify: `tests/test_official_slot.py`

- [x] **Step 1: Write failing alias tests**

Add official-style examples for:

```text
3日均线, 30日均线, 120日均线, 200日均线, 250日均线, 半年均线, 一年均线
5日均量线, 10日均量线, 20日均量线, 30日均量线, 60日均量线, 一周均量线, 一个月均量线, 一个季度均量线
委差
涨停炸板
涨停未封板
历史最大跌幅 / 历史最大回撤
大单买入金额 / 大单卖出金额
```

Expected first run: unsupported indicator failures or missing SQL fragments.

- [x] **Step 2: Add only schema-backed mappings**

Use these sources:

```text
委差 = base.commissionBuy - base.commissionSale
涨停炸板 = COALESCE(ext.lmtUpNum, 0) > 0 OR COALESCE(ext.boardBreaks, 0) > 0
涨停未封板 = 炸板条件 AND base.limitFlag != 1
历史最大跌幅/历史最大回撤/最大回撤 = ext.maxRetreat / 10000.0
大单买入金额 = ext.bigBuyTur
大单卖出金额 = ext.bigSellTur
```

Do not add `长上影线` in this task because the official package gives `upperShadow` but does not define the threshold for "长". That belongs in a later configurable-pattern design.

- [x] **Step 3: Re-run targeted tests**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_slot.py -q
```

Expected: official slot tests pass and generated SQL references `tech.ma30`, `tech.volume_avg_60`, `base.commissionBuy - base.commissionSale`, `ext.maxRetreat / 10000.0`, `ext.lmtUpNum`, and `ext.boardBreaks`.

## Task 3: Coverage Refresh and Documentation

**Files:**
- Modify: `docs/20_官方真实数据适配分析与开发计划.md`
- Modify: `docs/21_官方真实数据冲刺计划与验收闭环.md`
- Modify: `README.md`

- [x] **Step 1: Refresh official workbook coverage**

Run:

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports\official_slot_coverage.json --report-output reports\official_slot_coverage.md --sample-size 50 --json
```

Expected: `parse_ok` remains 5792 and `compile_ok` should not decrease from 1607. Any increase must be reported as grounded by official fields, not described as full coverage.

- [x] **Step 2: Update docs with exact numbers**

Document the new baseline, newly supported aliases, and still-open blockers. Keep the warning that real official Doris evidence is not final until the three official CSVs are imported and benchmarked.

## Task 4: Fresh Verification and Git Backup

**Files:**
- Repository root

- [x] **Step 1: Run full verification**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
```

Expected: full test suite passes.

- [x] **Step 2: Inspect git diff**

Run:

```powershell
git status --short
git diff -- src/findsl/official_slot.py tests/test_official_slot.py tests/test_official_doris_assets.py deploy/doris/official/04_feature_tables.sql
```

Expected: only planned files changed.

- [x] **Step 3: Commit and push**

Use a focused commit message:

```powershell
git add README.md docs/20_官方真实数据适配分析与开发计划.md docs/21_官方真实数据冲刺计划与验收闭环.md docs/superpowers/plans/2026-06-10-official-real-data-second-pass.md src/findsl/official_slot.py tests/test_official_slot.py tests/test_official_doris_assets.py deploy/doris/official/04_feature_tables.sql
git commit -m "feat: expand official real-data aliases"
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
$env:ALL_PROXY='socks5://127.0.0.1:7897'
git push
```

Expected: remote `main` contains the new grounded official-data milestone.

## Spec Coverage Self-Review

- Official real workbook coverage is addressed by Task 3.
- Official Doris SQL assets are addressed by Task 1.
- Official field-backed mappings are addressed by Task 2.
- Unsupported data domains remain explicitly diagnosed; no task introduces fake financial/fund/index/user-account data.
- Real official Doris evidence remains a separate blocker until Docker/Doris is running and the three large CSVs are imported.
