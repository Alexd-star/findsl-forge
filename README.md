# FinDSL Forge

FinDSL Forge is an enterprise-grade prototype for the 2026 Graduate FinTech Innovation Competition topic:

> Topic 19: Compile stock-screening DSL into high-performance Apache Doris SQL.

The project goal is not to let an LLM freely hallucinate SQL. The core path is deterministic:

```text
DSL -> Lexer/Parser -> Typed AST -> Semantic Validation -> SQL Plan -> Doris SQL
```

LLM/NL2DSL can be added as an assistant layer later, while the compiler remains auditable, reproducible, and testable.

## Current MVP Scope

- Parse nested stock-screening DSL expressions.
- Validate indicators, functions, named parameters, and window arguments from configuration.
- Compile `filter`, `then`, `rank`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, and `MIN` into SQL.
- Generate trace metadata explaining the selected rewrite path.
- Run without non-standard Python dependencies.
- Provide pytest coverage for parser, semantic validation, and SQL generation.

## Quick Start

```powershell
python -m pytest
python -m findsl.cli compile 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))'
python -m findsl.cli evaluate --input data/samples/queries.jsonl --output reports/evaluation_report.md
```

If running from the repository root without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
```

## Competition-Oriented Design

This repository is built around the topic's quantitative requirements:

- SQL correctness target: `>= 95%`
- Compile P95 target: `< 50ms`
- Long-range acceleration target: `10x+`
- New indicator/function target: core compiler code change `0 lines`

The first commit establishes a reliable compiler kernel. Later phases will add Doris execution, prefix-sum routing, benchmark reports, a web demo, and NL2DSL repair loops.
