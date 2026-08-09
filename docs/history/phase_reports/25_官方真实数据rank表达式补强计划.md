# 官方真实数据 rank 表达式补强计划

## 1. 为什么要补 rank 表达式

官方 DSL 规范允许函数之间做四则运算。真实 workbook 里有一批样例把 `rank(...)` 当作数值参与计算，例如“涨停天数排名 + 跌停天数排名”“集合竞价金额排名 / 集合竞价匹配量排名”“主力净流入排名 / 主力净流出排名”。当前项目只支持两种 rank 形态：一种是顶层 `rank(...) <= 10`，另一种是 `then rank(...) <= 10`。当 rank 出现在加减乘除表达式里时，编译器会把它当成普通函数处理，但 `_expr_sql()` 目前没有 rank 分支，于是报 `UNSUPPORTED_OFFICIAL_FUNCTION: rank`。

这不是数据缺失问题，而是表达式编译能力还不够完整。尤其是 `涨停天数`、`跌停天数`、`集合竞价金额`、`集合竞价匹配量`、`主力净流入`、`主力净流出`、`最高价`、`最低价`、`收盘价` 等指标已经在三张官方表里有字段或可推导表达式，继续报“rank 函数不支持”会影响赛题完成度。

## 2. 语义边界

本轮支持的是“当前股票在某个排名集合中的排名号”。例如：

```text
rank('', '', '涨停天数', 'desc', '本周', '', '', '')
```

在普通表达式里会被解释成：对本周满足约束的股票按涨停天数降序排序，找到当前 `base.mktcode/base.tgtcode/base.bizdate` 对应行的 `rank_no`，然后把这个 `rank_no` 作为一个数值参与外层计算。

这和现有顶层 rank 语义是一致的，只是以前顶层 rank 直接生成 `WHERE rank_no <= N`，现在表达式 rank 生成一个标量子查询返回 `rank_no`。

## 3. 不做的事情

本轮不支持 `rank(..., count_exp)` 在四则表达式中使用。这个语义涉及“某个股票在多个时间桶里连续/出现满足排名条件”的统计，需要专门的时间排名特征或窗口聚合；简单塞一个标量子查询会把时间含义压扁。

本轮不把缺字段指标包装成可执行 SQL。例如 `rank('', '', '归母净利润', ...)`、`rank('', '', '营业收入', ...)`、`rank('', '', '龙虎榜上榜次数', ...)` 仍然应该报未支持指标，因为官方三表没有这些字段。

本轮不改变已有顶层 rank 的 SQL。普通 `rank(...) <= 10` 已经有直接查询形态，性能和可读性都更好，没必要退化成标量子查询。

## 4. 实现方案

在 `_expr_sql()` 中新增 `rank` 分支。当 rank 出现在表达式位置时，调用 `_rank_scalar_expr()`。这个函数复用 `_rank_expr_without_count_exp()` 获取排名指标表达式和约束，再把指标表达式中的 `base/code/ext/tech` 别名改写为排名子查询内部的 `rb/rcode/rext/rtech`。最终生成的 SQL 大致如下：

```sql
(SELECT ranked.rank_no
 FROM (
   SELECT rb.mktcode, rb.tgtcode, rb.bizdate,
          ROW_NUMBER() OVER (
            PARTITION BY rb.bizdate
            ORDER BY <rank_expr> DESC, rb.tgtcode ASC
          ) AS rank_no
   FROM newzl.hsj_stock_hq_basic AS rb
   LEFT JOIN ...
   WHERE <rank constraints>
 ) AS ranked
 WHERE ranked.mktcode = base.mktcode
   AND ranked.tgtcode = base.tgtcode
   AND ranked.bizdate = base.bizdate)
```

这样外层表达式可以继续做 `+`、`-`、`*`、`/` 和普通比较。

## 5. 预期效果

动态均线补强后，官方覆盖率已经从 1718 条提升到 1751 条。本轮 rank 表达式补强后，`UNSUPPORTED_OFFICIAL_FUNCTION: rank` 应低于原来的 31 条。实际提升不会等于 31 条，因为其中不少样例后续会遇到财务、基金、龙虎榜、主力拆单、暗盘资金等缺字段指标。

本轮最有希望转为可编译的样例包括：涨停天数与跌停天数排名组合、集合竞价金额与匹配量排名比值、主力净流入与主力净流出排名比值、最高价/最低价/收盘价排名组合等。这些都是三表可落地的行情或资金类指标。

## 6. 执行结果

实现完成并重新刷新官方覆盖率后，`UNSUPPORTED_OFFICIAL_FUNCTION: rank` 已经从错误码汇总中消失。覆盖率在动态均线阶段为 1751 条，加入 rank 表达式后提升到 1766 条。随后补充 `每手股数` 和 `是否T+0` 两个交易规则常量，最终本轮覆盖率提升到 1804 条。

没有被转为成功的 rank 样例主要不是 rank 编译器问题，而是后续暴露了缺字段指标。例如 `归母净利润`、`营业收入`、`龙虎榜上榜次数`、`波动率`、`分红金额` 等仍然需要官方额外数据表，不能在当前三表上伪造。
