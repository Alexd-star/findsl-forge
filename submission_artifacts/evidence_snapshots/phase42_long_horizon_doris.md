# Phase 42 官方 20 年数据长周期加速证据

- 状态：`PASS`
- Git HEAD：`1146cf0a4cce9b89409285ea194f50024de7d8cb`
- 官方基础行情：`13650347` 行，`2006-01-04` 至 `2026-04-14`
- 月分区滚动特征表：`13650347` 行，`244` 个分区
- 完整结果集：`5487` 行，SHA-256 一致 `True`
- 基线中位耗时：`932.0` ms
- 优化中位耗时：`23.0` ms
- 实测加速：`40.522x`，目标 `>=10.0x`

## 测量口径

耗时取自 Doris Query Profile 的 `Summary.Total`，每次查询均关闭 SQL Cache，并在 Profile 中反向确认 `Is Cached: No`。基线与优化查询交替执行，避免固定先后顺序造成系统偏差。正确性使用完整、有序结果集 SHA-256，而非只比较行数。

## 计划证据

- 基线分区比：`[[1, 1]]`
- 优化分区比：`[[1, 244]]`
- 优化查询命中交易月单分区；基线必须扫描全量 20 年行情并执行排序与窗口聚合。

## 基线 SQL

```sql
SELECT w.mktcode,w.tgtcode,w.bizdate
FROM (
  SELECT
    base.mktcode,
    base.tgtcode,
    base.bizdate,
    SUM(base.volume) OVER (
      PARTITION BY base.mktcode,base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS volume_sum_20
  FROM newzl.hsj_stock_hq_basic AS base
) AS w
WHERE w.bizdate = DATE '2026-04-14'
  AND w.volume_sum_20 > 10000000
ORDER BY w.mktcode,w.tgtcode,w.bizdate
```

## 优化 SQL

```sql
SELECT p.mktcode,p.tgtcode,p.bizdate
FROM newzl.hsj_stock_hq_basic_rollup AS p
WHERE p.bizdate = DATE '2026-04-14'
  AND p.volume_sum_20 > 10000000
ORDER BY p.mktcode,p.tgtcode,p.bizdate
```
