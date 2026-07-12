# Phase 21 新增成功集假阳性审计

- 状态：`PASS`
- 新增成功：`99`
- 全部检查通过：`99`
- 检查失败：`0`

## 策略分布

| 策略 | 数量 |
|---|---:|
| `aggregate_rank` | 7 |
| `composite_grouped_aggregate` | 9 |
| `controlled_expression` | 13 |
| `crossing_window` | 1 |
| `direct_column` | 5 |
| `grouped_aggregate` | 1 |
| `set_intersect` | 29 |
| `stable_key_join` | 18 |
| `temporal_grouped_aggregate` | 6 |
| `temporal_rank` | 10 |

## 审计合同

逐条重新编译 Phase 20 失败而 Phase 21 成功的问句，并检查：后端 AST 验证通过；不存在 `1=0/1=1` 占位谓词；近似比较包含配置化容差表达式；聚合函数同时进入 Physical IR 和 SQL；`CONS/EXIST` 进入时序关系；`rank` 生成真实窗口排名。
