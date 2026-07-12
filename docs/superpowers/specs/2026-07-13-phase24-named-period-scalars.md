# Phase 24：命名周期末标量关系

## 1. 阶段目标

Phase 24 解决非聚合指标带多行日期窗口、同时又与聚合值或排名表达式参与同一条件时的作用域问题。此前规划器只允许锚点标量来自一个确定日期；“近五日成交量”或“上周 ST 标识”不能被当作单行值，因此返回 `PHYSICAL_SCALAR_SCOPE_UNBOUNDED`。直接放宽限制会产生多行 Join、重复证券和任意行比较，不能接受。

本阶段引入命名周期末标量关系，明确规定：未声明聚合函数的周期标量以窗口内最大 `bizdate` 对应的值作为周期末值，每只证券最多产生一行。

## 2. Physical IR 合同

`PhysicalNamedScalar` 增加两个结构化属性：

- `collapse_latest`：是否使用 `MAX_BY(value,bizdate)` 折叠周期；
- `group_by_security`：是否按 `(mktcode,tgtcode)` 生成每证券标量。

普通 `indicator` 周期标量同时启用两个属性。指定唯一证券的 `queryData` 周期标量启用 `collapse_latest`，但不按证券分组，因为证券身份约束后整个关系只应产生一个值。

`PhysicalRankExpression` 也可以携带命名标量，使“周期指标条件 + 多个排名算术”不需要退化成普通行过滤。

## 3. 规划规则

只有以下调用会被识别为周期标量：

1. 函数为 `indicator` 或具备精确证券身份的 `queryData`；
2. `agg_func` 与 `count_exp` 均为空；
3. 日期合同不是单个精确日期、今日/昨日或单交易日偏移；
4. 指标存在受控 Physical Catalog 或 Physical Expression 映射。

每个调用保留自己的市场、证券范围和日期约束。普通证券标量的结果关系按安全稳定键回连锚点；`queryData` 必须由安全目录解析为唯一证券，随后作为单行标量 CROSS JOIN。未知证券、多个证券或缺失数据仍返回结构化错误。

## 4. SQL 形态

每证券周期标量生成如下集合关系：

```sql
SELECT mktcode,
       tgtcode,
       MAX_BY(metric_value, bizdate) AS scalar_value
FROM constrained_source
GROUP BY mktcode, tgtcode
```

指定证券周期标量省略分组键，只输出一个 `MAX_BY` 值。后端不会使用无序 `MAX(value)`、不带日期的 `ANY_VALUE` 或相关标量子查询。

## 5. 复合聚合与排名

在 `PhysicalCompositeAggregate` 中，聚合组、周期标量和锚点快照分别物化，再按证券稳定键连接后执行最终谓词。周期标量不会被加入聚合函数本身，也不会改变其他聚合调用的日期范围。

在 `PhysicalRankExpression` 中，排名关系独立计算全体排名，周期标量独立折叠，最后和锚点按证券键连接。排名总体不会因周期标量的历史行数被放大。

## 6. 官方工作簿结果

Phase 23 基线为 `660/1097`。Phase 24 达到 `667/1097（60.80%）`，新后端总成功数为 687。旧严格成功集中七条 `PHYSICAL_SCALAR_SCOPE_UNBOUNDED` 全部迁移；全部工作簿共有十条由失败转为 backend success，审计结果为 `10/10 PASS`。

## 7. 真实 Doris 结果

`scripts/collect_phase24_period_scalar_evidence.py` 在真实 Doris 数据上验证四组非空用例：周期末值与周期 AVG 比较、两个周期标量和一个聚合共同计算、指定证券周期标量 CROSS JOIN，以及周期标量与两个排名关系组合。

预采集结果为 `4/4` 完整结果集 SHA-256 一致且全部非空。每组参考 SQL 独立写出 `MAX_BY`、分组键、日期范围和排名窗口，不复用编译器 AST。

## 8. 当前边界

事件与聚合/时序组合仍需独立的跨日期候选集合同。直接把事件日期行和最新快照做三列 `INTERSECT` 会漏掉历史窗口事件；只按证券键合并又可能把“某天未发生事件”误解为“窗口内从未发生事件”。Phase 25 将先明确事件量词和输出日期，再扩展 Physical IR。

缺失证券范围、行业成员和数据域继续返回结构化诊断，不能用周期标量关系掩盖数据不存在的问题。
