# Phase 47 大盘基准政策独立 Doris 证据

- 状态：`PASS`
- Git HEAD：`cdb6729d937f511c35c5df4fc39d3a8b2189a064`
- 官方行情锚点：`2026-04-14`
- 基准政策：`a-share-broad-market-v1`
- 大盘映射：`沪深300 (000300)`
- 指数行情快照：`akshare-sina-index-2026-07-15-42e29790031f`
- 锚点日指数记录：`1`
- 独立参考 SQL 完整行集一致：`3/3`
- 结构合同：`3/3`
- 性能门禁：`3/3`

| Excel 行 | 场景 | 参考行数 | 生成行数 | 哈希一致 | 结构合同 | P95/ms |
|---:|---|---:|---:|---|---|---:|
| 1870 | `ai_top1_not_outperform_benchmark` | 0 | 0 | PASS | PASS | 614.9537 |
| 4741 | `today_gain_between_benchmark_and_one_percent` | 0 | 0 | PASS | PASS | 242.6622 |
| 5742 | `recent_month_benchmark_and_ma60` | 786 | 786 | PASS | PASS | 1611.4436 |

> 参考 SQL 独立写出沪深300基准值、AI 范围排名、近一月末值和 60 日均线条件；完整比较 `(mktcode,tgtcode,bizdate)` 行集，不以行数或抽样代替语义核验。

> “大盘=沪深300”是版本化项目业务政策，不冒充赛题方唯一口径。赛题方若指定其他基准，只需替换政策目录和对应行情快照，无需修改 ANTLR、Typed AST、Logical IR、Physical IR 或 SQL 后端。
