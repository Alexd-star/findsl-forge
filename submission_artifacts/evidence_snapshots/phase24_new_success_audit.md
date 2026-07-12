# 编译器新增成功集假阳性审计

- 状态：`PASS`
- 新增成功：`10`
- 全部检查通过：`10`
- 检查失败：`0`

## 策略分布

| 策略 | 数量 |
|---|---:|
| `composite_grouped_aggregate` | 9 |
| `named_rank_expression` | 1 |

## 审计合同

逐条重新编译基线失败而当前版本成功的问句，并检查：后端 AST 验证通过；不存在 `1=0/1=1` 占位谓词；近似比较包含配置化容差表达式；聚合函数同时进入 Physical IR 和 SQL；`CONS/EXIST` 进入时序关系；`rank` 生成真实窗口排名；命名周期标量显式携带 `collapse_latest` 合同并生成 `MAX_BY`。
