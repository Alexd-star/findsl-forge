# 声明式新函数盲扩展证据

- Git HEAD：`dd61d10a39adfaf720720254df0a9bb557255b25`
- 新函数：`blind_demo_margin`
- 核心代码哈希（扩展前）：`1b9b91f0db5ddc371453f5cca4eb5d20a20e383601383062f4f9cc55b242db01`
- 核心代码哈希（扩展后）：`1b9b91f0db5ddc371453f5cca4eb5d20a20e383601383062f4f9cc55b242db01`
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
