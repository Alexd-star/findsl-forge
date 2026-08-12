# 声明式指标与函数复合盲扩展证据

- Git HEAD：`56430ca07c40e211bae9650c79be0e67ba125d11`
- 新指标：`盲扩展成交量`
- 新函数：`blind_demo_in_band`
- 仅声明配置发生变化：`True`
- 变更配置：`official/functions.json, official/indicators.json, official/physical_catalog.json, official/physical_statistics.json, official/physical_strategies.json`
- 核心代码哈希（扩展前）：`42a425224651366805ac07639f479ab7352b05ce8177dcb4e593608778054780`
- 核心代码哈希（扩展后）：`42a425224651366805ac07639f479ab7352b05ce8177dcb4e593608778054780`
- 核心代码未修改：`True`
- 类型错误拦截：`True`（`OFFICIAL_FUNCTION_ARG_TYPE`）
- 编译与 SQL 安全校验：`True`
- Gate：`PASS`

## 演示 DSL

```text
blind_demo_in_band(indicator('', '', '盲扩展成交量', '今日', '', '', ''), 1000000, 100000000) = True
```

## 生成 SQL

```sql
SELECT `q`.`mktcode`, `q`.`tgtcode`, `q`.`bizdate` FROM `newzl`.`hsj_stock_hq_basic` AS q WHERE (`q`.`volume` >= 1000000 AND `q`.`volume` <= 100000000) = TRUE AND `q`.`bizdate` = (SELECT MAX(`q_latest`.`bizdate`) FROM `newzl`.`hsj_stock_hq_basic` AS q_latest)
```
