# Phase 17 类型化排名真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`0f3db8648a54f2d50966d91e3aab79dbb9a38aaa`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- 基础行情表：`13650347` 行
- 完整行集哈希一致：`5/5`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |
|---|---:|---:|---|---:|
| direct_top_10 | 10 | 10 | 是 | 41.1927 |
| direct_top_10_percent | 562 | 562 | 是 | 55.7313 |
| aggregate_avg_top_10 | 10 | 10 | 是 | 45.132 |
| aggregate_avg_top_10_percent | 562 | 562 | 是 | 52.1759 |
| rank_scalar_intersection | 10 | 10 | 是 | 45.4781 |

> reference SQL 独立使用 ROW_NUMBER、COUNT、CEIL、GROUP BY 和集合交集。百分比边界按实际候选集基数向上取整；聚合排名先形成每证券度量，再执行窗口排名。并列值由 mktcode、tgtcode 稳定裁决。
