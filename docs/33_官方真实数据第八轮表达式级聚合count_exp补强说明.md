# 官方真实数据第八轮表达式级聚合 count_exp 补强说明

生成时间：2026-06-10

## 0. 2026-07-06 后续更新

本文件记录的是第八轮补强时的历史状态，当时官方 workbook 可落地编译数为 `1,873`，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 为 `14`。后续在 2026-07-06 已继续补齐官方 Excel 中 7 条可判定标点噪声、可由日频三表解释的区间/连续区间 `count_exp`，并新增官方真实数据逐问句性能矩阵。最新覆盖率已经刷新为：官方样例 `5799` 条，语法解析 `5799/5799`，可落地 Doris SQL `1882` 条，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 剩余 `3` 条。剩余 3 条和 1 条周期函数缺口已经在 `docs/35_官方三表缺失数据域不可伪造SQL审计报告.md` 中逐条说明，不能用假字段或无依据排序强行编译。

## 1. 本轮为什么继续做这一项

第七轮复核后，官方真实 workbook 中仍有 15 条 `UNSUPPORTED_OFFICIAL_COUNT_EXP`。重新逐条扫描后可以确认，大部分缺口并不适合继续开发：有的没有排名指标，有的是 `CONS=1-2月`、`EXIST=2-5` 这类官方规范没有明确定义的次数区间，有的是 `CONS=10分钟` 这种需要分钟级序列的数据，有的叠加了财务、基金、公司画像或预测指标。直接把这些样例“编译成功”会降低项目可信度。

本轮真正值得做的是 Excel 第 1178 行：

```text
indicator('沪', '分拆预期板块', '外盘', '6月15号的后3日', '', 'AVG', 'CONS=每日')
/ indicator('沪', '分拆预期板块', '每手股数', '6月15号的后3日', '', '', '') < 80000
```

这个样例的指标来源是清楚的。`外盘` 来自官方基础行情表 `hsj_stock_hq_basic.outerVol`，`每手股数` 在当前官方适配里是确定性常量 `100`。它不需要财务表、不需要基金表、不需要账户数据，也不需要分钟级行情。因此它属于“官方三表真实可落地，但编译器表达式结构还没覆盖”的缺口，应当继续补齐。

## 2. 语义拆解

这类表达不能按普通指标比较处理。它的实际含义是：

1. 在同一个股票、同一个日期窗口内取若干交易日；
2. 按 `count_exp` 的单位把窗口切成 bucket，本轮只实现官方样例需要的“每日 bucket”；
3. 对带 `agg_func` 和 `count_exp` 的指标在每个 bucket 内计算聚合值，例如 `AVG(外盘)`；
4. 对同一 scope 内的普通指标取该 bucket 的日内值，例如 `每手股数`；
5. 在 bucket 层计算表达式 `AVG(外盘) / 每手股数 < 80000`；
6. 再根据 `CONS=每日` 判断每个 bucket 是否都满足表达式。

这样做的关键是不要把聚合值提前算成一个窗口总值，也不要把 `count_exp` 当成普通行级过滤。正确的 SQL 形态应该是“先得到 bucketed 行，再统计 bucketed 行上的谓词”。

## 3. 实现内容

本轮在 `src/findsl/official_slot.py` 中新增表达式级聚合 `count_exp` 编译路径。核心变化包括：

1. `CountExpSpec` 增加 `agg_func` 字段，用于区分普通 `count_exp` 和聚合 `count_exp`。
2. `_count_exp_specs_from_node()` 不再忽略带 `agg_func` 的 `indicator(..., count_exp)`，从而能在算术表达式中识别这类槽位。
3. `_count_exp_expression_comparison_sql()` 检测到聚合 `count_exp` 后，转入 `_aggregate_count_exp_expression_comparison_sql()`。
4. 新路径只支持单一 market/filter/date/select/count_exp scope，避免把不同窗口或不同范围的值硬拼在一起。
5. 新路径只支持每日 bucket。周、月、季度、年 bucket 与普通指标混合时语义更复杂，暂不伪造支持。
6. 新路径对增长率聚合保持显式不支持，因为每日增长率需要 `LAG()` 语义，不能用普通 `AVG/SUM/MAX/MIN` 聚合套壳。

生成的核心 SQL 形态如下：

```sql
SELECT DATE_TRUNC(wb.bizdate, 'day') AS bucket_key,
       AVG(wb.outerVol) AS agg_0,
       MAX(100) AS value_0
FROM newzl.hsj_stock_hq_basic AS wb
WHERE wb.mktcode = base.mktcode
  AND wb.tgtcode = base.tgtcode
  AND wb.bizdate BETWEEN ...
GROUP BY DATE_TRUNC(wb.bizdate, 'day')
```

外层再使用：

```sql
SUM(CASE WHEN (bucketed.agg_0 / bucketed.value_0) < 80000 THEN 1 ELSE 0 END) = COUNT(*)
```

这与官方 `CONS=每日` 的含义一致：窗口内每个可见日 bucket 都需要满足表达式。

## 4. 测试与覆盖结果

新增单测：

```text
test_compile_aggregate_count_exp_inside_arithmetic_expression_uses_bucket_rows
```

红测阶段，旧实现会在 `_indicator_expr()` 抛出：

```text
count_exp must be compiled together with a comparison: CONS=每日
```

实现后，该测试通过，并检查以下关键 SQL 证据：

| 检查点 | 作用 |
|---|---|
| `DATE_TRUNC(wb.bizdate, 'day') AS bucket_key` | 证明按每日 bucket 聚合 |
| `AVG(wb.outerVol) AS agg_0` | 证明外盘均值进入 bucket |
| `MAX(100) AS value_0` | 证明每手股数作为同 bucket 值进入表达式 |
| `(bucketed.agg_0 / bucketed.value_0) < 80000` | 证明比较发生在 bucket 层 |
| `SUM(CASE WHEN ... THEN 1 ELSE 0 END) = COUNT(*)` | 证明 `CONS=每日` 不是普通计数，而是每日都满足 |

重新扫描官方 workbook 后，结果变为：

| 指标 | 变更前 | 变更后 |
|---|---:|---:|
| 可落地编译为 Doris SQL | 1,872 | 1,873 |
| `UNSUPPORTED_OFFICIAL_COUNT_EXP` | 15 | 14 |
| 第 1178 行 | 不支持 | 可编译 |

这个提升只有 1 条，但价值很明确：它补的是官方真实数据能支撑的复杂表达式结构，而不是靠假字段提高数字。

## 5. 剩余 14 条为什么暂不继续硬做

剩余 `count_exp` 缺口主要是以下几类：

1. `rank(..., indicator_name='', count_exp)`：没有排名指标，无法定义连续保持某个名次的排序口径。
2. `CONS=1-2月`、`CONS=3-7月`、`EXIST=2-5`：官方规范只定义单次数或“每”，没有给出次数区间的严格口径。
3. `CONS=10分钟`：官方数据是日频行情，没有 9:15-9:25 的逐分钟价格序列。
4. `position(..., count_exp)` 叠加缺字段：部分样例又叠加控股股东、散户数量、未分配利润、IOPV 等缺失数据。
5. `rank(...) inside arithmetic expressions with count_exp`：代表样例涉及营业收入和预测营业收入，当前官方三表没有字段来源。

因此，下一步不应为了覆盖率强行编译这些样例。更稳妥的方向是继续提升已支持 SQL 的 Doris 执行证据、表达式边界测试、文档解释、答辩可视化证据，以及真实数据导入后的性能演示。

## 6. 后续建议

后续如果继续从 `count_exp` 入手，建议只做两类：

1. 官方规范明确、字段真实存在、单位为日/周/月/季度/年的单次数表达；
2. 已有技术特征表能够确定性构建的表达，例如长周期均线、成交量均线、创新高/新低等。

对于区间次数和分钟级数据，应等赛题组补充说明或补充数据后再做。当前项目的竞争力不在于声称“什么都支持”，而在于它对官方真实数据的边界判断清楚，能执行的 SQL 有真实 Doris 证据，不能执行的意图有结构化、可答辩的原因。
