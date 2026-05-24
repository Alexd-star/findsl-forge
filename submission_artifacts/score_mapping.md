# 赛题得分点映射

| 得分点 | 实现位置 | 证据 | 演示动作 |
|---|---|---|---|
| DSL 词法、语法、AST | `src/findsl/lexer.py`, `parser.py`, `ast_nodes.py` | `official_suite_report.md`, `evaluation_report.md` | Web Demo 查看 AST 标签页 |
| 语义检查和错误提示 | `src/findsl/semantic.py`, `diagnostics.py` | 负例套件、诊断 smoke | 选择 UNKNOWN_INDICATOR 负例，看修复建议 |
| Doris SQL 生成 | `src/findsl/sqlgen.py`, `doris_sql.py` | SQL/reference 等价报告、Doris SQL validation | 展示 SQL 标签页和 `DORIS_SQL_VALIDATION` explain |
| 复杂选股算子 | `CONS`, `EXIST`, `MA`, `MAX`, `MIN`, `SUM`, `RET`, `rank`, `then`, `date_between` | 官方风格正例套件 | 依次演示连续资金流、窗口突破、收益率、排名、日期裁剪 |
| 结果正确性 | `reference.py`, `executor.py`, `equivalence.py` | `sql_equivalence_report.md`, readiness gate | 展示 verification PASS |
| 长窗口性能优化 | prefix-sum rewrite, hot-window materialized column `volume_sum_120` | `doris_cluster_evidence.md` | 展示 5M Doris 36x 级加速证据 |
| Doris 物理设计 | `deploy/doris/*.sql`, `docs/doris_runbook.md` | schema asset integrity, EXPLAIN | 展示 auto partition、hash bucket、colocate group |
| 真实行情业务样本 | `data/real_samples/eastmoney_a_share_sample/`, `scripts/fetch_real_market_sample.py` | Eastmoney raw JSON、metadata、SQL/reference 验证 | 展示真实股票代码和交易日期下的收益率 DSL |
| AI 大模型辅助 | `nl2dsl.py`, `llm_adapter.py` | NL2DSL smoke、LLM safety smoke | 输入中文需求，展示候选 DSL 通过验证 |
| 防幻觉和安全边界 | LLM 只产 DSL 候选，禁止直接 SQL | `UNSAFE_DIRECT_SQL` 拒绝证据 | 展示 mock LLM 响应中直接 SQL 被拒绝 |
| 可复现工程交付 | `scripts/*.ps1`, Git, artifact export | readiness、bundle、evidence snapshots | 运行 readiness/export 脚本 |

## 评审表述重点

本项目不是简单把自然语言交给大模型生成 SQL，而是把大模型限定在“候选 DSL 生成”阶段。所有候选必须经过确定性编译器、语义检查、SQL 安全边界、样例等价验证和 Doris 执行证据，既利用大模型提升交互效率，又保留金融系统需要的可审计性和稳定性。
