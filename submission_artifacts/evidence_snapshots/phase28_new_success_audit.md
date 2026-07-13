# 编译器新增成功集假阳性审计

- 状态：`PASS`
- 新增成功：`39`
- 全部检查通过：`39`
- 检查失败：`0`

## 策略分布

| 策略 | 数量 |
|---|---:|
| `crossing_window` | 26 |
| `crossing_window_absence` | 5 |
| `event_candidate_intersect` | 3 |
| `set_intersect` | 4 |
| `temporal_event_projection` | 1 |

## 审计合同

逐条重新编译基线失败而当前版本成功的问句，并检查：后端 AST 验证通过；不存在 `1=0/1=1` 占位谓词；近似比较包含配置化容差表达式；聚合函数同时进入 Physical IR 和 SQL；`CONS/EXIST` 进入时序关系；`rank` 生成真实窗口排名；命名周期标量显式携带 `collapse_latest` 合同并生成 `MAX_BY`；事件组合显式声明证券键集合与最新快照输出策略；扩展日期、分数量词和开放分页必须进入 Typed/Physical 合同并在 SQL 中可见。
