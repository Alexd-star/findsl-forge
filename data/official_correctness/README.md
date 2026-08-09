# 官方 SQL 正确率基准

本目录只保存进入正式正确率分母的冻结用例合同和独立 reference SQL。自动抽样、编译成功或旧管线成功均不能直接成为“正确”样例；只有 `eligibility=eligible`、`review_status=approved`、政策版本和数据快照一致且 reference SQL 文件存在的用例才参与评分。

`manifest.jsonl` 在独立语义复核完成前不得伪造 240 条已批准记录。候选样例应先写入开发报告或单独的 pending 文件，reference SQL 需要在不查看生成 SQL的前提下编写并复核。

当前 `manifest.jsonl` 收录 126 条去重后的历史阶段独立 reference SQL，覆盖官方 12 类函数，均保留原阶段报告、Git HEAD、结果行数和完整行集 SHA-256 于 `provenance.json`。这些用例已经通过历史双 SQL 行集一致性审计和当前编译链路复编译检查，但仍需在当前 Git HEAD、统一 Doris 快照上重跑，才能形成当前正式正确率。内部 240 条目标不能靠复制或微调同一问句凑数，新增用例必须补足函数族低覆盖项、边界语义和计划族。
