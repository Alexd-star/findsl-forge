# 官方真实数据逐问句性能矩阵

本文由 `reports/official_doris_evidence.json` 生成，只汇总已经在本地 Apache Doris 上真实执行并记录行数、耗时和 EXPLAIN 标记的查询。它用于补充赛题中“SQL 执行筛选结果不高于 10s”的逐问句证据，不替代原始 Doris evidence。

## 摘要

- Doris evidence 生成时间：`2026-06-09T17:45:34Z`
- 查询数量：6
- 全部查询 P95 <= 10s：True
- 最大 P95：61.269 ms
- 平均 Avg：45.492 ms
- baseline/prefix 行数一致：True
- baseline vs prefix speedup：1.173x

## 官方三表行数

| 表名 | 行数 |
|---|---:|
| hsj_stock_hq_ext | 6170822 |
| hsj_stock_hq_basic | 13650347 |
| hsj_stock_code_info | 5686 |

## 逐问句性能矩阵

| Query | Rows | Avg ms | P95 ms | Plan | 10s Target |
|---|---:|---:|---:|---|---|
| simple_close_price_filter | 3836 | 41.518 | 47.384 | ordinary | PASS |
| rank_volume_top10 | 10 | 49.361 | 57.073 | window | PASS |
| technical_long_window_feature_filter | 5614 | 53.816 | 61.269 | ordinary | PASS |
| ext_main_net_inflow_filter | 2247 | 46.139 | 57.988 | ordinary | PASS |
| baseline_window_volume_sum_20 | 5487 | 44.321 | 55.058 | window | PASS |
| prefix_optimized_volume_sum_20 | 5487 | 37.8 | 38.786 | prefix | PASS |

## 解释口径

- `ordinary` 表示普通过滤或 join 查询，没有显式窗口或 prefix 表。
- `window` 表示 EXPLAIN 或 SQL 中出现窗口执行路径，可作为 baseline 或排名类查询证据。
- `prefix` 表示 SQL/EXPLAIN 使用官方 prefix 特征表，是长窗口优化路径证据。
- `10s Target` 仅说明该条 evidence 中记录的 P95 是否低于赛题 10 秒目标；最终答辩仍应保留原始 SQL、EXPLAIN 和 JSON 作为审计来源。
