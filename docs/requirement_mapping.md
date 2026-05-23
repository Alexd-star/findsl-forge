# Requirement Mapping

This document maps Topic 19 requirements to implementation modules.

| Competition Requirement | Implementation Module | Evidence Status |
|---|---|---|
| Parse full stock-screening DSL and compound semantics | `findsl.lexer`, `findsl.parser`, `findsl.ast_nodes` | Implemented and regression-tested |
| Generate standard AST | `findsl.ast_nodes` | Implemented and exposed in demo/API |
| Compile DSL logic into Doris SQL | `findsl.sqlgen`, `findsl.doris_sql`, `DORIS_SQL_VALIDATION` explain evidence | Implemented with required readiness gate |
| Support cross-sectional ranking cutoffs | `findsl.sqlgen`, `findsl.reference`, `rank(..., top/bottom/percent)` official cases | Implemented with SQL/reference equivalence |
| Support signed financial thresholds | `findsl.lexer`, `findsl.parser`, `findsl.sqlgen`, signed net-outflow official cases | Implemented with diagnostics coverage |
| Support date-range partition pruning predicates | `date_between(...)`, `findsl.sqlgen`, `findsl.reference`, `DATE_RANGE_PUSHDOWN`, `DATE_RANGE_BASE_PRUNING`, and window-safe `DATE_RANGE_WINDOW_PRUNING` explain evidence | Implemented with explain evidence |
| Support CTE and window function rewrites | `findsl.sqlgen` | Implemented with window-safe feature layers |
| Decouple business rules from compiler core | `configs/*.json`, `findsl.registry` | Implemented |
| Add new indicators without core code changes | `configs/indicators.json`, `Registry`, defense-package config-only `alpha_score` extension check | Implemented with defense evidence |
| Compile P95 < 50ms | `findsl.compiler`, `findsl.evaluation` | Implemented; readiness P95 is below target |
| Long-range 10x acceleration using prefix sum/materialized paths | `findsl.sqlgen`, `findsl.scale_benchmark`, `findsl.doris_evidence` | Optimizer implemented; final 10x claim requires real Doris evidence |
| Prefix-sum optimized rolling SUM | `findsl.sqlgen`, `configs/indicators.json`, `configs/tables.json` | Implemented with quote and money-flow prefix cases |
| Baseline versus optimized performance evidence | `findsl.benchmark`, `scripts/benchmark_prefix_sum.ps1` | Implemented as local regression evidence |
| Reproducible long-window scale evidence | `findsl.synthetic`, `findsl.scale_benchmark`, `scripts/scale_benchmark.ps1` | Implemented as local scale evidence |
| Real Doris EXPLAIN and latency proof | `findsl.doris_evidence`, `collect-doris-evidence` CLI, `scripts/collect_doris_evidence.ps1` | External cluster evidence pending |
| Explainable optimizer decisions | `findsl.explain`, `findsl.sqlgen`, `findsl.evaluation`, `findsl.benchmark` | Implemented and surfaced in reports/demo |
| Doris deployment assets | `findsl.doris`, monthly `trade_date` auto partitions, `ts_code` colocate group, `scripts/generate_doris_assets.ps1`, `deploy/doris/*.sql` | Implemented with asset-integrity gate |
| Output Markdown table and engineering screenshots | `findsl.readiness`, `findsl.demo`, `scripts/submission_readiness.ps1`, `scripts/serve_demo.ps1` | Reports implemented; final screenshots/video are manual capture |
| AST/SQL/explain/result visualization | `findsl.demo`, `scripts/serve_demo.ps1`, readiness demo smoke gate | Implemented with API smoke gate |
| AI-assisted natural-language entry without SQL hallucination | `findsl.nl2dsl`, `findsl.demo`, `findsl.readiness`, `suggest-dsl` CLI | Implemented with compiler-validated templates |
| Optional LLM assistance with deterministic safety guardrails | `findsl.llm_adapter`, `validate-llm-candidates` CLI, `scripts/validate_llm_candidates.ps1`, `data/samples/llm_candidate_response.json`, readiness required gate | Implemented with unsafe-SQL rejection |
| Interactive error explainability and repair guidance | `findsl.diagnostics`, `findsl.demo`, `diagnose` CLI, Web Demo diagnostic presets | Implemented with negative official suite |
| Official-style task coverage and negative diagnostic evidence | `findsl.official_suite`, `official-suite` CLI, `scripts/official_suite.ps1`, `data/samples/official_*_cases.jsonl`, readiness required gate | Implemented: 25/25 positive and 26/26 negative |
| Defense walkthrough and score-mapping evidence | `findsl.defense_package`, `defense-package` CLI, `scripts/defense_package.ps1`, `reports/defense_package.md`, readiness required gate | Implemented with 11/11 defense checks |
| Reproducible evaluation report | `findsl.evaluation`, `scripts/evaluate.ps1` | Implemented |
| Semantic correctness proof | `findsl.reference`, `findsl.executor`, `findsl.equivalence`, sample CSV tables | Implemented with required readiness gate |
| Local SQL execution regression | `findsl.executor`, `scripts/verify_sql_sample.ps1` | Implemented |
| Submission package evidence chain | `findsl.readiness`, `scripts/submission_readiness.ps1`, `reports/*.md`, `reports/doris_cluster_evidence.md` | Implemented except final Doris cluster proof |
| Git rollback and backup discipline | git history, `docs/git_workflow.md`, backup bundles | Implemented and continuously maintained |
