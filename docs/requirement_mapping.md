# Requirement Mapping

This document maps Topic 19 requirements to implementation modules.

| Competition Requirement | Implementation Module | MVP Status |
|---|---|---|
| Parse full stock-screening DSL and compound semantics | `findsl.lexer`, `findsl.parser`, `findsl.ast_nodes` | Started |
| Generate standard AST | `findsl.ast_nodes` | Started |
| Compile DSL logic into Doris SQL | `findsl.sqlgen` | Started |
| Support CTE and window function rewrites | `findsl.sqlgen` | Started |
| Decouple business rules from compiler core | `configs/*.json`, `findsl.registry` | Started |
| Add new indicators without core code changes | `configs/indicators.json` | Started |
| Compile P95 < 50ms | `findsl.compiler`, `findsl.evaluation` | Started |
| Long-range 10x acceleration using prefix sum/materialized paths | `findsl.sqlgen`, `findsl.scale_benchmark`, `findsl.doris_evidence` | Started |
| Prefix-sum optimized rolling SUM | `findsl.sqlgen`, `configs/indicators.json`, `configs/tables.json` | Started |
| Baseline versus optimized performance evidence | `findsl.benchmark`, `scripts/benchmark_prefix_sum.ps1` | Started |
| Reproducible long-window scale evidence | `findsl.synthetic`, `findsl.scale_benchmark`, `scripts/scale_benchmark.ps1` | Started |
| Real Doris EXPLAIN and latency proof | `findsl.doris_evidence`, `collect-doris-evidence` CLI, `scripts/collect_doris_evidence.ps1` | Started |
| Explainable optimizer decisions | `findsl.explain`, `findsl.sqlgen`, `findsl.evaluation`, `findsl.benchmark` | Started |
| Doris deployment assets | `findsl.doris`, `scripts/generate_doris_assets.ps1`, `deploy/doris/*.sql` | Started |
| Output Markdown table and engineering screenshots | `findsl.readiness`, `findsl.demo`, `scripts/submission_readiness.ps1`, `scripts/serve_demo.ps1` | Started |
| AST/SQL/explain/result visualization | `findsl.demo`, `scripts/serve_demo.ps1`, readiness demo smoke gate | Started |
| AI-assisted natural-language entry without SQL hallucination | `findsl.nl2dsl`, `findsl.demo`, `findsl.readiness`, `suggest-dsl` CLI | Started |
| Interactive error explainability and repair guidance | `findsl.diagnostics`, `findsl.demo`, `diagnose` CLI, Web Demo diagnostic presets | Started |
| Official-style task coverage and negative diagnostic evidence | `findsl.official_suite`, `official-suite` CLI, `scripts/official_suite.ps1`, `data/samples/official_*_cases.jsonl`, readiness required gate | Started |
| Reproducible evaluation report | `findsl.evaluation`, `scripts/evaluate.ps1` | Started |
| Semantic correctness proof | `findsl.reference`, `findsl.executor`, `findsl.equivalence`, sample CSV tables | Started |
| Local SQL execution regression | `findsl.executor`, `scripts/verify_sql_sample.ps1` | Started |
| Submission package evidence chain | `findsl.readiness`, `scripts/submission_readiness.ps1`, `reports/*.md`, `reports/doris_cluster_evidence.md` | Started |
| Git rollback and backup discipline | git history, `docs/git_workflow.md`, backup bundles | Started |
