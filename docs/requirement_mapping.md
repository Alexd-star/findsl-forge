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
| Output Markdown table and engineering screenshots | future UI/report modules | Planned |
| Reproducible evaluation report | `findsl.evaluation`, `scripts/evaluate.ps1` | Started |
