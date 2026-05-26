# 答辩 PPT 逐页大纲

## 1. 标题页

FinDSL Forge：面向 Apache Doris 的可审计金融选股 DSL 编译与加速系统。

## 2. 赛题痛点

- 金融筛选条件复杂，包含窗口、收益率、连续性、排名、日期裁剪和多表指标。
- 直接让大模型生成 SQL 不稳定，不适合金融可审计场景。
- 长窗口滚动计算在大规模行情数据上容易成为性能瓶颈。

## 3. 总体方案

自然语言入口只生成候选 DSL；确定性编译器负责词法、语法、语义、AST、Doris SQL、验证和 explain。核心链路可审计、可测试、可回溯。

## 4. 系统架构

展示四层：

1. 输入层：DSL / 中文自然语言 / 离线 LLM 候选 / OpenAI-compatible provider 候选。
2. 编译层：lexer、parser、semantic、registry、sqlgen。
3. 验证层：Pandas reference、SQLite regression、Doris SQL validation。
4. 执行层：Apache Doris schema、prefix table、EXPLAIN、latency evidence。

## 5. DSL 能力

展示 `filter`, `then`, `rank`, `CONS`, `EXIST`, `MA`, `MAX`, `MIN`, `SUM`, `RET`, `date_between`，并给出一个复杂组合样例。

## 6. Doris SQL 生成

展示从 DSL 到 CTE/window/rank SQL 的转换，强调稳定排序、日期下推、多表 join 和 SQL literal escaping。

## 7. 正确性验证

展示 SQL/reference 等价验证、官方风格正例、负例诊断、readiness gate。

## 8. 长窗口优化

说明 baseline window plan 与 prefix-sum plan 的差异：从重复窗口扫描变成前缀表查找或 hot-window materialized column。

## 9. 性能证据

放 `doris_cluster_evidence.md` 中的数字：5,000,000 行、baseline/optimized 平均耗时、P95、行数一致、speedup。

## 10. AI 辅助但不放弃安全

展示 NL2DSL、LLM safety loop 和 provider contract：接受合法 DSL，拒绝 direct SQL 和未知指标；真实 provider 输出仍作为候选进入同一套验证。

## 11. 工程化交付

展示 Docker Doris、PowerShell 自动化脚本、真实行情小样本、Git 回溯、bundle 备份、submission artifact 快照。

## 12. 创新点总结

- 面向金融 DSL 的确定性编译和可解释优化。
- 大模型只做候选生成，系统负责审计和拒绝。
- Doris 物理设计和 prefix-sum 优化结合，形成真实性能证据。
- 端到端 readiness gate 支撑比赛交付。

## 13. 后续扩展

- 扩大真实行情覆盖范围，并补充真实资金流数据。
- 扩展更多财务、公告、新闻情绪指标。
- 多 FE/BE Doris 集群、自动化 Stream Load 和物化视图维护。
