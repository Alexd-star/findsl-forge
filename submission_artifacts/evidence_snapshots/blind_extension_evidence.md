# 声明式新函数盲扩展证据

- Git HEAD：`a323d96ca63728b4ac9dbba3d5599c56a6cd135d`
- 新函数：`blind_demo_margin`
- 核心代码哈希（扩展前）：`93ee33f10a153ccff2a68d4b05ed23083140bb0af75c72378e3f23b778fa38e5`
- 核心代码哈希（扩展后）：`93ee33f10a153ccff2a68d4b05ed23083140bb0af75c72378e3f23b778fa38e5`
- 核心代码未修改：`True`
- 编译与 SQL 安全校验：`True`
- Gate：`PASS`

## 演示 DSL

```text
blind_demo_margin(indicator('', '', '收盘价', '今日', '', '', ''), indicator('', '', '最低价', '今日', '', '', ''), 0.01) = True
```

## 生成 SQL

```sql
SELECT `q`.`mktcode`, `q`.`tgtcode`, `q`.`bizdate` FROM `newzl`.`hsj_stock_hq_basic` AS q WHERE (((`q`.`closePx` / 10000.0) - (`q`.`lowPx` / 10000.0)) / NULLIF(ABS(`q`.`lowPx` / 10000.0), 0)) >= 0.01 = TRUE AND `q`.`bizdate` = (SELECT MAX(`q_latest`.`bizdate`) FROM `newzl`.`hsj_stock_hq_basic` AS q_latest)
```
