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
| `real_market_sample.png` | Eastmoney 真实行情样例、PASS 状态、SQL 行数和真实日期条件 | 说明真实股票代码和交易日期也走同一套编译与 SQL/reference 验证链路 |
| `08_official_stage_rank_physical_ir.png` | 官方七槽 DSL、`stage_rank` 策略和真实 Physical IR | 证明页面直接操作 ANTLR/IR/SQLGlot 新后端，而不是只展示旧编译器 |
| `09_official_t0_expected_rejection.png` | T+0 缺失数据负例、失败阶段、预期/实际诊断码与禁用复制按钮 | 说明系统不会用日频数据伪造 T+0 SQL，失败仍可审计 |
| `10_official_t0_mobile.png` | 390px 移动端完整官方负例页面 | 证明窄屏布局、诊断可读性和无页面横向溢出 |

生成或录制一分钟答辩视频时，建议先用 `01 -> 02 -> real_market_sample` 说明内部验证闭环，再切换 `08 -> 09` 展示官方编译架构与诚实拒绝边界，最后用 `06` 收束到 Doris 性能证据。`scripts/build_defense_video.py` 中的旧路线仍可复现历史视频；重新录制时应优先采用当前双管线界面。
