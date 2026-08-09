# 官方真实数据 then 复合排名阶段补强说明

## 1. 问题背景

第三轮官方 workbook 覆盖率刷新后，项目已经完成动态日均线、动态日均量线、`rank(...)` 算术表达式、`每手股数` 和 `是否T+0` 等三表可落地能力，官方样例编译成功数达到 1804 条。继续分析剩余失败样例时可以看到，绝大多数仍然是官方三张 CSV 没有覆盖的数据域，例如财务报表、基金持仓、指数成分、公司画像、用户持仓和龙虎榜数据。这些内容不能靠编译器硬造字段，否则 SQL 虽然看起来能生成，实际无法在 Doris 上执行，也经不起答辩追问。

但仍有一类问题属于 DSL 形态能力不足，而不是数据缺失：`then` 右侧不再只是一个简单的 `rank(...) <= N`，而是复合条件。例如：

```text
indicator('沪', '', '涨停', '8号', '', '', '') = True
then rank('沪', '', '总市值', 'desc', '8号', '', '', '') = 3
and indicator('沪', '', 'ST股票标识', '8号', '', '', '') = False
```

再比如：

```text
indicator('沪主板|深主板', '', '开盘价', '', '', '', '') < 2
then (
  rank('沪主板|深主板', '', '开盘价', 'asc', '', '', '', '') <= 20
  or rank('沪主板|深主板', '', '开盘价', 'desc', '', '', '', '') <= 20
)
```

旧实现把 `then` 右侧限定为单个 rank 比较，所以这类样例会停在 `OFFICIAL_RANK_SHAPE_ERROR` 或 `OFFICIAL_EXPR_ERROR`。这不是赛题数据不支持，而是编译管线对官方 DSL 的组合形态理解不够完整。

## 2. 语义判断

`A then B` 在本项目中解释为“先用 A 得到候选集，再在候选集内执行 B”。因此，`then` 右侧如果出现 rank，rank 的排序范围必须是上一阶段的候选集，而不是全市场。否则 SQL 可以生成，但含义会错。例如“涨停股里市值第三”不能写成“全市场市值第三且涨停”，这两个结果完全可能不同。

本轮补强遵循这个原则：

1. 单个 `then rank(...) <= N` 继续走原有高效路径，避免影响既有稳定 SQL。
2. `then rank(...) between '[a,b]'` 会生成上一阶段候选集内的排名区间判断。
3. `then rank(...) and 普通过滤` 会在上一阶段候选集内重新排名，再叠加右侧普通条件。
4. `then (rank A or rank B)` 会把两个 rank 条件都限定在同一个上一阶段候选集内。
5. 带 `rank(..., count_exp)` 的复合 then 暂不强行落地，因为它需要时间桶排名特征表或物化 rank feature table；当前三表虽然有日频行情，但没有直接给出跨时间排名聚合结果。

## 3. 实现内容

代码修改集中在 `src/findsl/official_slot.py`。

新增 `_compile_then_condition_stage()`，用于处理 `then` 右侧不是单个 rank 比较的情况。它先生成 `stage_0` CTE 保存左侧预筛选结果，再生成 `stage_1`，从 `stage_0` 回连 `hsj_stock_hq_basic` 并执行右侧复合条件。

新增 `_then_condition_sql()`，递归处理 `and/or` 组合。如果遇到 rank 比较，则不调用普通全市场 rank 条件，而是交给 `_then_rank_condition_sql()`。

新增 `_then_rank_condition_sql()`，在 `stage_0` 或上一阶段 CTE 内重新计算 `ROW_NUMBER()`。核心结构如下：

```sql
EXISTS (
  SELECT 1 FROM (
    SELECT rb.mktcode, rb.tgtcode, rb.bizdate,
           ROW_NUMBER() OVER (
             PARTITION BY rb.bizdate
             ORDER BY <rank_expr> DESC, rb.tgtcode ASC
           ) AS rank_no
    FROM stage_0 AS prev_rank
    INNER JOIN newzl.hsj_stock_hq_basic AS rb
      ON rb.mktcode = prev_rank.mktcode
     AND rb.tgtcode = prev_rank.tgtcode
     AND rb.bizdate = prev_rank.bizdate
    ...
  ) AS ranked
  WHERE ranked.mktcode = base.mktcode
    AND ranked.tgtcode = base.tgtcode
    AND ranked.bizdate = base.bizdate
    AND <rank_no predicate>
)
```

新增 `_rank_no_predicate()`，统一生成 `rank_no <= N`、`rank_no = N`、`rank_no between '[a,b]'` 等谓词。这样 `then rank between` 不再误走普通 literal 解析，也不会因为右侧是 `OfficialRangeLiteral` 而报表达式错误。

## 4. 测试用例

本轮按 TDD 增加了 3 个测试，先确认失败，再实现转绿：

1. `test_compile_then_rank_between_uses_scoped_rank_stage`
   验证 `then rank between '[5,10]'` 能生成 `stage_0/stage_1`，且 rank 在 `stage_0` 内重新计算。

2. `test_compile_then_rank_and_plain_filter_stays_inside_prefiltered_stage`
   验证 `then rank = 3 and ST股票标识=False` 能同时保留排名条件和普通过滤条件。

3. `test_compile_then_grouped_rank_or_conditions_share_prefiltered_stage`
   验证 `then (rank asc <= 20 or rank desc <= 20)` 中两个 rank 都共享上一阶段候选集。

执行结果：

```text
python -m pytest tests\test_official_slot.py::test_compile_then_rank_between_uses_scoped_rank_stage tests\test_official_slot.py::test_compile_then_rank_and_plain_filter_stays_inside_prefiltered_stage tests\test_official_slot.py::test_compile_then_grouped_rank_or_conditions_share_prefiltered_stage -q
3 passed

python -m pytest tests\test_official_slot.py -q
63 passed
```

## 5. 官方覆盖率变化

刷新官方 `选股提槽实例.xlsx` 后，覆盖率结果如下：

| 指标 | 补强前 | 补强后 |
|---|---:|---:|
| 官方样例总数 | 5799 | 5799 |
| 语法解析成功 | 5792 | 5792 |
| 语法解析失败 | 7 | 7 |
| Doris SQL 编译成功 | 1804 | 1823 |
| Doris SQL 编译失败 | 3988 | 3969 |
| 全量样例可落地编译率 | 31.11% | 31.44% |
| 解析成功样例可落地编译率 | 31.15% | 31.47% |
| `OFFICIAL_RANK_SHAPE_ERROR` | 29 | 0 |
| `OFFICIAL_EXPR_ERROR` | 10 | 6 |

`UNSUPPORTED_OFFICIAL_INDICATOR` 从 3875 变为 3889。这个数字上升不是功能倒退，而是之前一部分样例停在 `then/rank` 形态错误，现在形态已经通过，继续暴露出更深层的缺字段指标，例如“归母净利润”“估值”“波动率”“我的自选股”。这种错误归因更适合答辩：项目能明确说明哪些是编译器问题，哪些是官方数据包缺失问题。

## 6. 剩余边界

当前仍不处理以下情况：

1. `rank(..., count_exp)` 出现在复合 `then` 条件中。它需要按时间桶计算候选集内排名，再统计连续或出现次数，建议后续通过物化 rank feature table 实现。
2. `rank(...) / rank(...) <= N` 出现在 `then` 右侧时，目前仍走普通 scalar rank 表达式路径，尚未完全限定到上一阶段候选集。这类样例数量很少，但属于后续可补强点。
3. `then` 被括号包在更大 `or/and` 表达式中，例如 `(A then rank) or (B then rank)`，当前仍属于复杂表达式组合，需要更大范围的查询 AST 到 CTE 计划重写。
4. 如果复合 then 右侧继续触发财务、基金、指数、画像、用户持仓等缺字段指标，仍应保持未支持，不应伪造 SQL。

## 7. 对赛题交付的意义

本轮补强的价值不只是增加 19 条覆盖率，而是把排名管线从“只能处理教学式单 rank”推进到“能处理真实官方语料中的复合筛选后排名”。对赛题 19 来说，这直接对应 DSL 到高性能 Doris SQL 的核心评分点：语义保持、可执行 SQL、可解释诊断和真实数据边界。

后续如果继续冲刺，建议优先做两个方向。第一是 `rank(..., count_exp)` 的物化时间排名特征表；第二是 `(A then rank) or (B then rank)` 这类多分支 CTE 查询规划。两者都能继续提升编译覆盖率，但实现复杂度明显高于本轮补强，需要保持测试先行。
