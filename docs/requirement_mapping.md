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
| Long-range 10x acceleration using prefix sum/materialized paths | future `findsl.optimizer` | Planned |
| Prefix-sum optimized rolling SUM | `findsl.sqlgen`, `configs/indicators.json`, `configs/tables.json` | Started |
| Baseline versus optimized performance evidence | `findsl.benchmark`, `scripts/benchmark_prefix_sum.ps1` | Started |
| Explainable optimizer decisions | `findsl.explain`, `findsl.sqlgen`, `findsl.evaluation`, `findsl.benchmark` | Started |
| Doris deployment assets | `findsl.doris`, `scripts/generate_doris_assets.ps1`, `deploy/doris/*.sql` | Started |
| Output Markdown table and engineering screenshots | `findsl.readiness`, `scripts/submission_readiness.ps1`, future UI modules | Started |
| Reproducible evaluation report | `findsl.evaluation`, `scripts/evaluate.ps1` | Started |
| Semantic correctness proof | `findsl.reference`, `findsl.executor`, `findsl.equivalence`, sample CSV tables | Started |
| Local SQL execution regression | `findsl.executor`, `scripts/verify_sql_sample.ps1` | Started |
| Submission package evidence chain | `findsl.readiness`, `scripts/submission_readiness.ps1`, `reports/*.md` | Started |
| Git rollback and backup discipline | git history, `docs/git_workflow.md`, backup bundles | Started |
