# FinDSL Forge Defense Package

## Summary

- Package passed: True
- Checks passed: 13/13
- Scope: local reproducible evidence for live defense; attach the latest Doris 10x+ proof from the exported evidence snapshots.

## Live Walkthrough

1. Start the demo with `powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1`.
2. Let the default Chinese request produce a validated DSL candidate and SQL/reference PASS.
3. Try `A股存在资金流入后按低价取每日2只`, `A股每日换手率前50%`, `B股近2日均量不低于80`, `2026-01-02到2026-01-04收盘价大于3日均线`, `主力净流出低于-1.5`, `近3日最低收盘价低于10`, `A股近2日收盘价涨幅超过5%`, and `2026-01-02到2026-01-04近3日成交量累计大于300`; confirm each suggested DSL validates.
4. Select `Official positive: 主力净流入3日滚动求和走资金流前缀表 [money_flow_prefix_sum]` and run it.
5. Confirm the UI shows verification PASS, optimizer `Applied`, and SQL containing `dwd_stock_money_flow_prefix`.
6. Select `Diagnostic negative: 未知指标名 [UNKNOWN_INDICATOR]` and run it.
7. Confirm the UI shows `Diagnostic`, expected/actual `UNKNOWN_INDICATOR`, and the `indicator("close")` repair hint.
8. Show the semantic hardening evidence for bare identifiers, invalid windows, invalid top-level expressions, bad market arguments, and literal division by zero.
9. Run `python -m findsl.cli validate-llm-candidates --response-file data\samples\llm_candidate_response.json --json` to prove the LLM path accepts only compiler-validated DSL.
10. If a provider key is available, run `python -m findsl.cli llm-suggest-dsl "近3日成交量累计大于300" --model <model> --json`; otherwise show the offline provider-contract check in this package.
11. Run the real-market quote sample verification from `data\real_samples\eastmoney_a_share_sample\queries.jsonl` to show the same checker works on public A-share fields.
12. Run `scripts\official_suite.ps1` and `scripts\submission_readiness.ps1` to show repeatable report evidence.

## Score Mapping

| Check | Scoring point | Passed | Demo action | Expected signal | Evidence |
|---|---|---:|---|---|---|
| NL2DSL validated candidate | AI-assisted entry without SQL hallucination | True | Use the default Chinese request in the Web Demo. | Candidate is validated and verification is PASS. | candidate_count=1<br>top_dsl=then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))<br>sql_rows=2 |
| NL2DSL official template coverage | AI-assisted coverage for bottom-rank, percent-rank, B-market average-volume, date-window, signed-threshold, rolling-min, return-rate, and prefix-pruning official scenarios | True | Enter official-style Chinese prompts for low-price bottom, turnover percent, B-market average volume, date-window MA, net-outflow threshold, rolling-min, close-return, and date-prefix-sum cases. | Each prompt yields a compiler-validated DSL candidate whose rule matches the intended official scenario. | covered=8/8<br>low_price_bottom: rule=money_flow_low_price_rank, validated=True<br>turnover_percent: rule=turnover_percent_rank, validated=True<br>b_market_average_volume: rule=volume_ma_threshold, validated=True<br>date_window_pruning: rule=date_range_close_above_ma, validated=True<br>signed_outflow_threshold: rule=net_outflow_threshold, validated=True<br>rolling_min_threshold: rule=close_rolling_min_threshold, validated=True<br>close_return_threshold: rule=close_return_threshold, validated=True<br>date_prefix_sum_pruning: rule=date_range_rolling_volume_sum, validated=True |
| LLM candidate safety loop | LLM assistance with deterministic compiler guardrails | True | Run validate-llm-candidates against data\samples\llm_candidate_response.json. | One valid DSL is accepted, direct SQL is rejected, and misspelled indicators produce diagnostics. | accepted=1<br>rejected=2<br>rejected_codes=UNKNOWN_INDICATOR, UNSAFE_DIRECT_SQL<br>response=D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\data\samples\llm_candidate_response.json |
| OpenAI-compatible LLM provider contract | Real-provider AI entry point without relaxing deterministic safety | True | Use llm-suggest-dsl with a configured provider, or inspect this offline provider-contract check. | Provider prompt asks for JSON DSL only; returned candidates are validated by the same compiler and reference oracle. | endpoint=https://provider.example/v1/chat/completions<br>messages=2<br>json_response_format=True<br>prompt_contract=True<br>accepted=1<br>rejected=1<br>rejected_codes=UNSAFE_DIRECT_SQL |
| Official prefix-sum positive preset | Long-window optimization with explainable SQL rewrite | True | Select the money_flow_prefix_sum official positive preset and run it. | Verification PASS, optimizer Applied, and money-flow prefix table in SQL. | case=主力净流入3日滚动求和走资金流前缀表<br>compile_ms=0.992<br>sql_rows=3<br>sql_contains=dwd_stock_money_flow_prefix |
| Official diagnostic negative preset | Interactive error explainability and repair guidance | True | Select the UNKNOWN_INDICATOR negative preset and run it. | Expected and actual diagnostic codes match, with a close-indicator repair hint. | case=未知指标名<br>expected=UNKNOWN_INDICATOR<br>actual=UNKNOWN_INDICATOR<br>suggestions=2 |
| Semantic hardening diagnostics | Hidden-eval style invalid DSL fails before SQL generation with repairable diagnostics | True | Run the official negative corpus or select the hardening negative presets in the Web Demo. | Bare identifiers, invalid windows, bad top-level expressions, invalid market arguments, and static division by zero are rejected with stable hints. | hardened=6/6<br>裸指标列名绕过: code=SEMANTIC_ERROR, hint=True<br>窗口不是整数字面量: code=SEMANTIC_ERROR, hint=True<br>顶层表达式不是关系或布尔: code=SEMANTIC_ERROR, hint=True<br>市场参数不是字符串或标识符: code=SEMANTIC_ERROR, hint=True<br>除数为零字面量: code=SEMANTIC_ERROR, hint=True<br>除数为零常量表达式: code=SEMANTIC_ERROR, hint=True |
| Doris SQL validation boundary | Generated SQL shape and literal safety | True | Compile a market literal containing a quote and SQL-looking text. | DORIS_SQL_VALIDATION appears in explain with zero issues and the SQL literal is escaped. | validation_steps=1<br>issue_count=0<br>escaped_literal=True |
| Public real-market quote sample | Business credibility with real A-share codes and dates, separated from performance proof | True | Run the Eastmoney sample DSL cases under data\real_samples\eastmoney_a_share_sample. | All quote-only DSL cases pass SQL/reference equivalence with cached raw JSON and source metadata present. | source=Eastmoney public historical K-line endpoint<br>raw_payloads=2<br>cases=3/3<br>real_quote_turnover: passed=True, rows=9<br>real_quote_return_rate: passed=True, rows=5<br>real_quote_volume_sum: passed=True, rows=7 |
| Config-only indicator extension | New indicator support without compiler-core changes | True | Compile a temporary registry extension containing indicator alpha_score. | Generated SQL references alpha_score and still passes Doris SQL validation. | indicator=alpha_score<br>sql_contains_indicator=True<br>doris_validation=True |
| Official-style coverage suite | Representative task coverage and negative-case proof | True | Run scripts\official_suite.ps1. | All official-style positive and negative cases pass. | positive=37/37<br>negative=37/37<br>report=D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\official_suite_report.md |
| Compiler accuracy and latency | Correct SQL generation under compile P95 target | True | Run scripts\evaluate.ps1 or submission_readiness.ps1. | 100% compile/fragment accuracy and P95 below 50 ms. | cases=10/10<br>fragments=100.00%<br>p95_ms=1.125 |
| Doris deployment asset integrity | Reproducible partitioned and colocated Doris deployment path | True | Run scripts\generate_doris_assets.ps1, then inspect deploy\doris. | All generated Doris SQL assets match, with auto partitions and colocated distribution visible in schema SQL. | matched=4/4<br>missing=<none><br>auto_partitions=True<br>colocated_distribution=True<br>asset_dir=D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\deploy\doris |

## Submission Narrative

- Deterministic compiler path keeps correctness auditable: DSL -> AST -> semantic validation -> Doris SQL.
- AI assistance is constrained to NL2DSL/LLM DSL candidates; every candidate must compile and match the independent reference oracle.
- The LLM adapter rejects direct SQL and invalid DSL with stable diagnostic evidence before any SQL reaches Doris.
- The optional OpenAI-compatible provider path is wired as a candidate source only; provider responses still enter the same safety loop.
- The compiler validates Doris-safe SQL shape and escapes string literals before generated SQL is accepted.
- Public Eastmoney quote samples show the product story on real A-share codes and dates, while performance claims remain tied to 5M Doris evidence.
- Prefix-sum optimization is visible in SQL, structured explain records, and benchmark/readiness evidence.
- Negative cases demonstrate controlled, repairable failure rather than uncaught exceptions.
- Semantic hardening evidence proves hidden-eval style invalid DSL fails before SQL generation.
- Generated Doris assets include trade-date auto partitions and colocated stock-code distribution from the same compiler registry.