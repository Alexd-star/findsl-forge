# 官方真实数据剩余缺口再分析与 OR 分支 then 补强计划

## 1. 当前状态

截至本轮分析，项目已经把官方 `选股提槽实例.xlsx` 中 5799 条样例重新跑通一遍。当前结果为：

| 指标 | 数值 |
|---|---:|
| 官方样例总数 | 5799 |
| 语法解析成功 | 5792 |
| 语法解析失败 | 7 |
| Doris SQL 编译成功 | 1823 |
| Doris SQL 编译失败 | 3969 |
| 全量样例可落地编译率 | 31.44% |
| 解析成功样例可落地编译率 | 31.47% |
| Blocking gates | PASS |
| Warning count | 0 |
| Pytest | 278 passed |

前几轮已经完成了几个关键补强：动态 `N日均线/N日均量线`、`rank(...)` 算术表达式、A 股 `每手股数/是否T+0` 规则常量、`then` 后复合 rank 条件。尤其是 `OFFICIAL_RANK_SHAPE_ERROR` 已经从 29 降到 0，说明“先筛选、再排名”的主要 DSL 形态已经基本打通。

## 2. 最新失败分层

最新错误码只剩下四类主要问题：

| 错误码 | 数量 | 当前判断 |
|---|---:|---|
| `UNSUPPORTED_OFFICIAL_INDICATOR` | 3889 | 最大头，绝大多数是官方三张 CSV 没有数据源 |
| `UNSUPPORTED_OFFICIAL_COUNT_EXP` | 56 | 时间连续/出现次数和排名时间桶语义仍需物化特征或更复杂子查询 |
| `UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION` | 18 | `record_high/record_low/position` 带复杂连续周期，部分可后续做特征表 |
| `OFFICIAL_EXPR_ERROR` | 6 | 只剩少量 then 嵌套在更大布尔表达式中的查询规划问题 |

这说明项目后续不能再按“见一个未支持指标就补一个字段”的方式推进。真正成熟的做法是先判断该指标是否能从官方真实三表或确定性派生表得到。如果不能，就必须保留明确诊断；如果能，就补编译器语义或派生特征。

## 3. 官方 Doris 最佳实践核对

本轮查阅了 Apache Doris 官方文档，用来确认后续 SQL 规划方向是否稳妥。

Apache Doris 官方 CTE 文档说明，CTE 可以在同一条 `SELECT` 语句中定义临时结果集，并可被后续查询引用；适合把深层嵌套子查询拆成命名阶段，也适合表达“后一步基于前一步计算结果”的逻辑。来源：[Apache Doris CTE 文档](https://doris.apache.org/docs/4.x/query-data/cte/)。

Apache Doris 官方窗口函数文档说明，窗口函数使用 `OVER` 子句，`PARTITION BY` 用于把输入拆成独立分组，`ORDER BY` 用于定义组内顺序；`ROW_NUMBER/RANK/LAG/LEAD` 等排名和相邻行函数都属于这一类。来源：[Apache Doris Analytic Functions](https://doris.apache.org/docs/dev/key-features/analytic-functions/) 与 [Window Functions Overview](https://doris.apache.org/docs/4.x/sql-manual/sql-functions/window-functions/overview/)。

这与项目当前策略一致：短链 `then rank` 用 `ROW_NUMBER() OVER (PARTITION BY bizdate ORDER BY ...)`；多阶段筛选用 CTE 拆成 `stage_0/stage_1/...`；对于 `rank(..., count_exp)` 这种跨时间桶排名，优先考虑物化 rank feature table，而不是在每条查询里重复大窗口计算。

## 4. 仍可继续补的高价值点

### 4.1 顶层 OR 合并 then 分支

最新 6 个 `OFFICIAL_EXPR_ERROR` 中，有一个样例完全可以由官方三表落地：

```text
(indicator('', '', '港股通标识', '', '', '', '') = True
 then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1)
or
(indicator('', '', '陆股通标识', '', '', '', '') = True
 then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1)
```

它的自然语言含义是“分别找南向通流入最大和北向通流入最大”。这不是一个单一候选集里的 OR 条件，而是两个独立筛选-排名查询的并集。最佳 SQL 形态应当是：

```sql
<港股通预筛选后排名第一>
UNION
<陆股通预筛选后排名第一>
```

这样可以保留每个分支各自的排名集合，不会把港股通和陆股通混成一个排序集合。

### 4.2 `rank(..., count_exp)` 时间排名特征表

官方样例中还有 56 个 `UNSUPPORTED_OFFICIAL_COUNT_EXP`。其中一部分是 `rank(..., count_exp)`，例如“近 15 天连续 3 天市盈率排名在 5%-10%”。这类语义不能简单用当前日排名代替，需要按天、周、月等时间桶计算排名，再统计满足条件的桶数量。后续可设计 `hsj_stock_rank_feature_daily` 之类的物化特征表，但需要谨慎控制表规模、指标集合和刷新成本。

### 4.3 `record_high/record_low/position` 连续周期特征

18 个周期函数失败多数是“连续 N 天创新高/新低”“连续处于底部”。如果指标是价格、成交额、量比、主力净流入等三表字段，可以通过派生表落地；但如果指标是 MACD、横盘天数、财务项，则仍缺数据源。建议后续只做价格/成交量/资金类子集。

## 5. 本轮实施范围

本轮先实现 4.1：顶层 `OR` 合并 then 分支。原因如下：

1. 它完全由当前三表字段支撑，不会引入伪指标。
2. 实现范围小，不会破坏现有单查询编译路径。
3. 可以把 `OFFICIAL_EXPR_ERROR` 从 6 进一步降低。
4. 语义上更正确：每个 then 分支独立排名，再用 `UNION` 合并。

暂不实现 4.2 和 4.3。它们价值高，但需要更多表设计、Doris 真实性能验证和更大测试集，不适合与这次小补强混在一起。

## 6. 预期验收

新增测试应覆盖：

```text
(indicator('', '', '港股通标识', '', '', '', '') = True
 then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1)
or
(indicator('', '', '陆股通标识', '', '', '', '') = True
 then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1)
```

通过标准：

1. SQL 中出现 `UNION`。
2. 两个分支各自保留 `ROW_NUMBER() OVER`。
3. 一个分支保留 `code.hkConnFlag = TRUE`，另一个分支保留 `code.hkConnFlag = TRUE` 或对应陆股通别名约束。
4. `ORDER BY ext.ZJLXMainNetTur DESC` 在两个分支内出现。
5. 全量 `tests/test_official_slot.py` 和全量 pytest 通过。
6. 官方 workbook 覆盖率刷新后，`OFFICIAL_EXPR_ERROR` 低于 6。

## 7. 后续路线

本轮完成后，下一批优先级建议如下：

| 优先级 | 方向 | 是否立即开发 | 原因 |
|---|---|---|---|
| P0 | 顶层 OR then 分支 UNION | 是 | 小范围、真实数据可落地、语义明确 |
| P1 | `rank(..., count_exp)` 物化排名特征 | 暂缓 | 需要表设计与 Doris 性能验证 |
| P1 | 价格/成交量/资金类连续 `record_high/low` | 暂缓 | 需确认官方字段和窗口口径 |
| P2 | 缺失财务/基金/指数/用户账户指标 | 不做伪实现 | 官方数据包没有来源 |
| P2 | 周/月 K 线口径 | 不做伪实现 | 需要重采样规则，不能把周/月误当日线 |

## 8. 本轮执行结果

按上述范围完成开发后，项目新增了两类可落地查询规划能力。

第一类是顶层 `OR` 中包含多个独立 `then` 分支时，编译器不再把它当成普通布尔表达式，而是把每个分支独立编译成完整查询，再用 `UNION` 合并结果。这样可以保留每个分支自己的候选集和排名空间，避免把两个“分别排名”的语义混成一个全局排名。

第二类是 `then` 出现在 `AND` 条件中时，编译器把该 `then` 查询编译为结果集成员判断：

```sql
EXISTS (
  SELECT 1
  FROM (
    <then query>
  ) AS then_result
  WHERE then_result.mktcode = base.mktcode
    AND then_result.tgtcode = base.tgtcode
    AND then_result.bizdate = base.bizdate
)
```

这个写法的含义是“当前候选行是否属于该 then 查询结果集”。它让普通筛选条件可以和一个独立的筛选后排名结果相交，同时不会改变原来单独 `then rank` 的 SQL 形态。

新增测试包括：

```text
test_compile_or_of_independent_then_rank_branches_uses_union
test_compile_then_branch_inside_and_as_membership_condition
```

验证结果：

```text
python -m pytest tests\test_official_slot.py -q
65 passed
```

刷新官方 workbook 后：

| 指标 | 补强前 | 补强后 |
|---|---:|---:|
| Doris SQL 编译成功 | 1823 | 1824 |
| Doris SQL 编译失败 | 3969 | 3968 |
| 全量样例可落地编译率 | 31.44% | 31.45% |
| 解析成功样例可落地编译率 | 31.47% | 31.49% |
| `OFFICIAL_EXPR_ERROR` | 6 | 0 |

需要解释的是，`OFFICIAL_EXPR_ERROR` 归零并不意味着这些样例都能落地。原来的 6 条里，只有“南向通流入最大、北向通流入最大”这一条完全由三表字段支撑，因此编译成功数只净增 1。其余样例继续暴露为 `UNSUPPORTED_OFFICIAL_INDICATOR`，例如“潜力”“热门”“经营性现金流”“上市日期”“发行价”“短期负债占比”。这比停在表达式错误更准确，因为评委能清楚看到：编译器已经理解该 DSL 形态，真正缺的是官方数据包没有提供相应字段。

本轮之后，官方覆盖报告中的失败类型已经收敛为三类：

1. 官方数据包没有字段来源的指标；
2. `count_exp` 跨时间桶排名/比较语义；
3. `record_high/record_low/position` 的复杂连续周期语义。

这三类都不适合靠简单映射硬补。后续如果继续冲刺，应优先设计时间排名物化特征表，并在 Doris 上重新采集性能证据。
