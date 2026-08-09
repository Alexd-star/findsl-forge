# 官方 SQL 正确率基准

本目录只保存进入正式正确率分母的冻结用例合同和独立 reference SQL。自动抽样、编译成功或旧管线成功均不能直接成为“正确”样例；只有 `eligibility=eligible`、`review_status=approved`、政策版本和数据快照一致且 reference SQL 文件存在的用例才参与评分。

`manifest.jsonl` 在独立语义复核完成前不得伪造 240 条已批准记录。候选样例应先写入开发报告或单独的 pending 文件，reference SQL 需要在不查看生成 SQL的前提下编写并复核。
