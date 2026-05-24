# Web Demo 截图索引

本目录保存可随提交包一起回溯的 Web Demo 截图。截图来自本地 `http://127.0.0.1:8765`，用于技术报告、PPT 和答辩视频剪辑，不替代 `reports/` 中的可执行证据。

| 文件 | 画面重点 | 答辩用途 |
|---|---|---|
| `01_nl_to_dsl_overview.png` | 中文自然语言输入、候选 DSL、样例选择和总体状态 | 说明系统入口不是手写 SQL，而是中文请求到受控 DSL |
| `02_positive_sql.png` | 正例 `PASS`、编译延迟、结果行数和 Doris SQL | 展示确定性编译链路与 SQL 可审计性 |
| `03_positive_ast.png` | 同一正例的 AST JSON | 证明系统理解表达式结构，而不是只做字符串替换 |
| `04_positive_explain.png` | 优化/编译 explain 记录 | 说明优化行为可解释、可复核 |
| `05_positive_rows.png` | SQL/reference 验证结果行 | 展示独立语义校验后的结果预览 |
| `06_positive_evidence.png` | Doris evidence 摘要 | 展示 5M 行 Doris 规模证据和性能结论入口 |
| `07_negative_unknown_indicator.png` | `UNKNOWN_INDICATOR` 负例，预期诊断与实际诊断一致 | 展示错误输入会被稳定诊断并给出修复建议 |

录制一分钟答辩视频时，建议按 `01 -> 02 -> 04 -> 05 -> 06 -> 07` 的顺序切换。这样能在短时间内讲清楚“AI 辅助输入、确定性编译、可解释优化、语义验证、Doris 规模证据、可修复诊断”六个得分点。
