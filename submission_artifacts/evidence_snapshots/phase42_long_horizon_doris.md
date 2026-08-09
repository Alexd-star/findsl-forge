# Phase 42 官方 20 年数据长周期加速证据

- 状态：`PASS`
- Git HEAD：`6f3bcaee5fb3b0fbd81d0f37984f55f964a7d0a9`
- 输入 DSL：`indicator('', '', '成交量', '近5000日', '', 'SUM', '') > 10000000`
- 编译目录快照：`0220ac16d8cdf779da910d7289bb979da84ea1328198ed7b7029bd09e6f1b636`
- 基线/优化策略：`grouped_aggregate` / `volume_prefix_aggregate`
- 官方基础行情：`13650347` 行，`2006-01-04` 至 `2026-04-14`
- 月分区滚动特征表：`13650347` 行，`244` 个分区
- 完整结果集：`5614` 行，SHA-256 一致 `True`
- 基线中位耗时：`342.0` ms
- 优化中位耗时：`21.0` ms
- 实测加速：`16.286x`，目标 `>=10.0x`

## 测量口径

耗时取自 Doris Query Profile 的 `Summary.Total`，每次查询均关闭 SQL Cache，并在 Profile 中反向确认 `Is Cached: No`。基线与优化查询交替执行，避免固定先后顺序造成系统偏差。正确性使用完整、有序结果集 SHA-256，而非只比较行数。

## 计划证据

- 基线分区比：`[[1, 1], [1, 1], [1, 1], [1, 1]]`
- 优化分区比：`[[1, 244]]`
- 基线和优化 SQL 均由同一 DSL、同一编译目录快照生成；优化计划使用前缀端点差分，基线计划对 20 年会话范围执行集合聚合。

## 基线 SQL

```sql
SELECT result_rows.mktcode,result_rows.tgtcode,result_rows.bizdate
FROM (
SELECT `anchor_out`.`mktcode`, `anchor_out`.`tgtcode`, `anchor_out`.`bizdate` FROM `newzl`.`hsj_stock_hq_basic` AS anchor_out INNER JOIN (SELECT `aggregate_rows`.`mktcode`, `aggregate_rows`.`tgtcode` FROM (SELECT `q`.`mktcode`, `q`.`tgtcode`, SUM(`q`.`volume`) AS `metric_value` FROM `newzl`.`hsj_stock_hq_basic` AS q WHERE `q`.`bizdate` IN (SELECT `calendar_sessions`.`bizdate` FROM `newzl`.`hsj_stock_hq_basic` AS calendar_sessions GROUP BY `calendar_sessions`.`bizdate` ORDER BY `calendar_sessions`.`bizdate` DESC LIMIT 5000) GROUP BY `q`.`mktcode`, `q`.`tgtcode`) AS aggregate_rows WHERE `aggregate_rows`.`metric_value` > 10000000) AS qualified_result ON `anchor_out`.`mktcode` = `qualified_result`.`mktcode` AND `anchor_out`.`tgtcode` = `qualified_result`.`tgtcode` WHERE `anchor_out`.`bizdate` = (SELECT MAX(`latest_anchor`.`bizdate`) FROM `newzl`.`hsj_stock_hq_basic` AS latest_anchor)
) AS result_rows
ORDER BY result_rows.mktcode,result_rows.tgtcode,result_rows.bizdate
```

## 优化 SQL

```sql
SELECT result_rows.mktcode,result_rows.tgtcode,result_rows.bizdate
FROM (
SELECT `q`.`mktcode`, `q`.`tgtcode`, `q`.`bizdate` FROM `newzl`.`hsj_stock_hq_basic_rollup` AS q WHERE `q`.`bizdate` = '2026-04-14' AND `q`.`volume_prefix` > 10000000
) AS result_rows
ORDER BY result_rows.mktcode,result_rows.tgtcode,result_rows.bizdate
```
