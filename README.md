# FinDSL Forge

FinDSL Forge is an enterprise-grade prototype for the 2026 Graduate FinTech Innovation Competition topic:

> Topic 19: Compile stock-screening DSL into high-performance Apache Doris SQL.

The project goal is not to let an LLM freely hallucinate SQL. The core path is deterministic:

```text
DSL -> Lexer/Parser -> Typed AST -> Semantic Validation -> SQL Plan -> Doris SQL
```

AI/NL2DSL is implemented as an assistant layer that proposes DSL candidates. Every candidate still flows through the deterministic compiler and SQL/reference equivalence check, so the core remains auditable, reproducible, and testable.

## ANTLR/IR Migration Status

The production-hardening branch now contains a second, strictly typed compiler path:

```text
ANTLR4 -> Typed AST -> Domain/Logical IR -> Rule Optimizer
       -> Physical IR -> SQLGlot Doris AST -> Doris validation/execution
```

On the official 5,799-row workbook, the current strict baseline remains 1,097 grounded legacy-backend queries. The new Physical IR/SQLGlot backend compiles 135 of that strict success set (`12.31%`) and succeeds on 136 workbook rows in total. This is a migration metric, not an overall SQL accuracy claim. Missing data domains still return `DOMAIN_DATA_UNAVAILABLE`; unsupported semantics return stage-specific diagnostics rather than placeholder SQL.

Phase 9 introduces typed trading-sequence semantics, typed date windows, relational set algebra, and gap-aware year/quarter/month/week buckets for `CONS/EXIST` predicates. The generated Doris plan is set based and uses CTE/window islands instead of correlated scalar subqueries or calendar-day `DATEDIFF`; independent `AND` branches become intersections and `OR` branches become distinct unions. On the official `13,650,347`-row basic quote table, an independent raw-row oracle matches Doris result hashes in all ten cases (`10/10`): six daily/set cases over the latest full stock universe and four calendar-bucket cases over a deterministic 200-stock sample. The highest measured P95 is about 1.30 seconds in the current five-run snapshot. See `submission_artifacts/evidence_snapshots/phase9_temporal_doris.md` and `phase9_temporal_funnel.md` for the versioned evidence, scope boundaries, and remaining migration gaps.

Phase 10 adds a same-entity multi-resource join planner. It derives a deterministic `official_basic` anchor, constructs a left-deep `PhysicalJoin` tree, and obtains every join key from the catalog-declared stable-key intersection. Static security metadata joins on `(mktcode,tgtcode)` while dated quote, flow, and technical resources also require `bizdate`. Five independently written reference joins match generated Doris result hashes (`5/5`) across two- and three-resource cases. Multi-resource temporal, aggregate, and cross-entity plans remain explicit failures until their own contracts are implemented. See `submission_artifacts/evidence_snapshots/phase10_join_doris.md` and `phase10_join_funnel.md`.

## Implemented Scope

- Parse nested stock-screening DSL expressions.
- Validate indicators, functions, named parameters, duplicate named arguments, and window arguments from configuration.
- Compile `filter`, `then`, `rank` with top/bottom/percent cutoffs, `date_between`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, `MIN`, and `RET` into SQL.
- Generate trace metadata explaining the selected rewrite path.
- Emit structured optimizer explain steps for machine-readable rewrite evidence.
- Validate generated SQL against a Doris-safe single-query shape before returning it.
- Return structured compile diagnostics and repair hints for invalid DSL/API requests.
- Prove config-only indicator extension through defense-package evidence.
- Execute generated SQL against local SQLite fixtures for regression checks.
- Compare SQL output with an independent Pandas semantic reference evaluator.
- Push safe date ranges and window-safe date upper bounds into base table scans for partition-pruning-friendly Doris SQL.
- Support signed numeric thresholds for net-flow and other negative-valued financial indicators.
- Normalize mixed-case indicator names and market codes for official-style input robustness.
- Preserve sparse auxiliary-table rows by anchoring stock-date semantics on `daily_quote` and left-joining optional tables.
- Rewrite eligible rolling `SUM` expressions to prefix-sum table joins for long-window acceleration.
- Use configured hot-window prefix columns such as `volume_sum_120` to avoid query-time prefix self-joins on competition-scale Doris evidence paths.
- Build auxiliary prefix tables from the daily quote trading-calendar skeleton so sparse money-flow data cannot shift rolling windows.
- Produce baseline-window versus prefix-sum benchmark reports.
- Generate deterministic synthetic A-share-style data for reproducible long-window scale benchmarks.
- Generate Doris DDL with trade-date auto partitions, colocated stock-code distribution, sample load, prefix-table build, and smoke-query assets.
- Collect Doris-cluster `EXPLAIN` and latency evidence for baseline-window versus prefix-sum SQL.
- Serve a local Web Demo/API for DSL, AST, Doris SQL, optimizer explain, and SQL/reference verification.
- Suggest DSL candidates from Chinese natural-language stock-screening requests, then validate them through the compiler and reference oracle.
- Cover official-style NL2DSL prompts for low-price bottom picks, turnover percent cuts, B-market average-volume thresholds, high-turnover close ranking, date-window moving-average filters, rolling minimum thresholds, return-rate thresholds, date-prefix-sum pruning, and signed net-outflow thresholds.
- Validate optional LLM-proposed DSL candidates while rejecting direct SQL and invalid DSL before execution.
- Call an optional OpenAI-compatible LLM provider as a DSL-candidate source, then force every returned candidate through the same deterministic safety loop.
- Run an official-style coverage suite with representative positive cases and negative diagnostic cases.
- Generate a defense package that maps live demo steps to competition scoring evidence.
- Generate a submission readiness report covering tests, accuracy, equivalence, optimizer evidence, real-market sample evidence, Doris assets, and git rollback state.
- Pin runtime dependencies, including the generated ANTLR4 frontend runtime, for reproducible installation.
- Provide pytest coverage for parser, semantic validation, SQL generation, and SQL/reference equivalence.

Current readiness passes required gates and the Doris-scale performance proof. The recorded Doris evidence uses 5,000,000 synthetic daily quote rows, disables Doris SQL cache during timing, and shows a 36.24x cluster speedup for a 120-day rolling-volume prefix path.

The repository also includes a versioned public A-share quote sample under `data/real_samples/eastmoney_a_share_sample/`. It uses Eastmoney historical K-line rows for 贵州茅台 and 平安银行 so the demo can show real market fields without mixing that small business sample with the 5M-row Doris performance claim.

The official Topic 19 real-data adapter is tracked separately from the staged internal DSL path. It reads the official `选股提槽实例.xlsx` workbook and the three `newzl` Doris CSV tables (`hsj_stock_code_info`, `hsj_stock_hq_basic`, `hsj_stock_hq_ext`), reports parse/compile coverage, and emits SQL only for indicators that can be grounded in the provided A-share tables or deterministic OHLCV-derived feature tables. On the current 5,799-row workbook, strict parsing succeeds for 5,792 rows and recovery parsing succeeds for all 5,799; strict compilation produces 1,097 grounded, non-degraded results, while recovery compilation produces 1,830 results. These are different evidence populations and must not be merged into a single success rate. The remaining strict failures are primarily unsupported indicators from data domains absent in the official three tables; `UNSUPPORTED_OFFICIAL_COUNT_EXP` is down to 3 and remains an explicit no-fake-SQL boundary. The official Doris path has also completed real CSV ingestion and feature-table construction on local Apache Doris: `hsj_stock_code_info=5,686`, `hsj_stock_hq_basic=13,650,347`, `hsj_stock_hq_ext=6,170,822`, and each official derived feature table has `13,650,347` rows. `scripts/prepare_official_doris_evidence.ps1` records row-count parity, feature-table parity, SQL/EXPLAIN evidence, and baseline/prefix row-count equivalence before writing `reports/official_doris_evidence.md/json`.

This count reflects real `agg_func/count_exp`, cross-date, rank-count, aggregate rank-count, crossed-line event count, aggregate count expressions inside arithmetic, punctuation-noise repair for documented workbook defects, bounded `count_exp` ranges, chained-rank, industry-aggregate, period-position, official alias, and string-wildcard semantics instead of treating unsupported intent as ordinary field filters. The adapter now normalizes official date slots, including explicit year ranges such as `2006年-12年`, month/day forms such as `2024年8月` and `9号`, colloquial recent windows such as `过去20天` and `三个月之内`, and composite relative forms such as `本月的前一周`, `2018年的第五年`, and `最近的第二天`, scales official integer price/rate fields into human units, preserves branch-local `OR` constraints, localizes incompatible `AND` date slots with correlated `EXISTS`, compiles AVG/SUM/MAX/MIN/GROWTH and EXIST/CONS windows for ordinary indicators, compiles grounded `rank(..., count_exp)` and `rank(..., agg_func, count_exp)` as bucketed rank counting, compiles `cross_above/cross_down/golden_cross(..., count_exp)` as daily event rows using `LAG()` while keeping pre-window source rows for first-day event correctness, maps moving-average/candlestick/volume-breakout indicators through `newzl.hsj_stock_hq_basic_technical`, supports monotonic `then rank(...) then rank(...)` pipelines as CTE stages, uses official `pxMkTopDays/pxMkBotDays` for price new-high/new-low predicates, maps grounded official aliases such as `涨停天数`、`涨停价`、`跌停价`、`沪港通标识`、`委比`、`委差`、`涨停炸板`、`涨停未封板`, long-window MA/volume-average aliases, and big-order amount aliases, emits valid `LIKE` SQL for `%...%` string wildcards, classifies unsupported official samples by missing data domain, and supports `belong_industry` for numeric indicators via `hyBlkRefName` aggregates. See `docs/20_官方真实数据适配分析与开发计划.md`, `docs/21_官方真实数据冲刺计划与验收闭环.md`, `docs/22_官方真实数据落库复盘与满分冲刺计划.md`, `docs/31_官方真实数据第六轮复核与后续计划.md`, `docs/32_官方真实数据第七轮窗口语义复核与后续开发计划.md`, `docs/33_官方真实数据第八轮表达式级聚合count_exp补强说明.md`, `docs/34_官方槽位DSL_BNF与ANTLR形式化说明.md`, `docs/35_官方三表缺失数据域不可伪造SQL审计报告.md`, `docs/superpowers/plans/2026-06-09-official-real-data-hardening.md`, `docs/superpowers/plans/2026-06-10-official-real-data-second-pass.md`, `docs/superpowers/plans/2026-06-10-official-doris-evidence-automation.md`, and `deploy/doris/official/` for the current official-data plan, schema, Stream Load runbook, smoke queries, feature-table SQL, grammar/audit materials, and evidence automation.

## Comprehensive Chinese Manual

The repository includes a long-form Chinese Word manual for competition submission and defense:

- `docs/FinDSL_Forge_中文综合操作指南.docx`
- `docs/FinDSL_Forge_中文综合操作指南.md`

The manual is written as a combined product introduction, project overview, architecture whitepaper, algorithm explanation, operation guide, deployment guide, validation report guide, and defense reference. Its source Markdown contains more than 30,000 Chinese characters and is generated by `scripts/build_chinese_manual_docx.py` for reproducibility.

## 中文文档与文件索引

为便于比赛提交、答辩复核、后续维护和代码回溯，项目根目录提供中文文件索引与分册式文档体系：

- `PROJECT_INDEX.md`: 当前项目文件、文件夹、运行入口、历史文件和维护建议总索引。
- `CHANGELOG.md`: 面向提交和维护的版本更新记录。
- `docs/README.md`: `docs/` 目录文档导航。
- `docs/01_项目简介.md`: 项目定位、目标用户、核心能力和交付价值说明。
- `docs/03_操作手册.md`: 命令行、Web Demo、验证脚本和 Doris 证据采集操作说明。
- `docs/12_环境依赖与部署.md`: Python、Doris、PowerShell 脚本和可选 LLM Provider 的环境说明。
- `docs/17_项目交付说明.md`: 提交物、验收顺序、答辩材料和人工复核事项说明。

## Quick Start

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m findsl.cli compile 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))'
python -m findsl.cli evaluate --input data/samples/queries.jsonl --output reports/evaluation_report.md
python -m findsl.cli reference 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(RET(indicator("close"), 2) > 0.05)' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json
python -m findsl.cli suggest-dsl '筛选A股连续三天主力净流入为正并按换手率排名前一百' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股存在资金流入后按低价取每日2只' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股每日换手率前50%' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'B股近2日均量不低于80' --data-dir data/samples --json
python -m findsl.cli suggest-dsl '主力净流出低于-1.5' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股近2日收盘价涨幅超过5%' --data-dir data/samples --json
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --text '近3日成交量累计大于300' --data-dir data/samples --json
python -m findsl.cli llm-suggest-dsl '近3日成交量累计大于300' --model '<provider-model>' --json
python -m findsl.cli official-suite --output reports/official_suite_report.md --json
python -m findsl.cli official-slot-coverage --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/official_slot_coverage.json --report-output reports/official_slot_coverage.md
python -m findsl.cli official-performance-matrix --evidence reports/official_doris_evidence.json --json-output reports/official_query_performance_matrix.json --report-output reports/official_query_performance_matrix.md --json
python -m findsl.cli defense-package --output reports/defense_package.md --json
python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.md
python -m findsl.cli scale-benchmark --stocks 300 --days 260 --window 120 --iterations 5 --output reports/prefix_sum_scale_benchmark.md
python -m findsl.cli collect-doris-evidence --host 127.0.0.1 --port 9030 --user root --database findsl_demo --dsl 'filter(SUM(indicator("volume"), 120) > 1000000)' --output reports/doris_cluster_evidence.md
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
python -m findsl.cli readiness-report --output reports/submission_readiness.md
python -m findsl.cli evidence-metadata --snapshots-dir submission_artifacts/evidence_snapshots --output submission_artifacts/evidence_metadata.json --summary-output submission_artifacts/evidence_summary.md
```

The official parser also has a pinned ANTLR4 shadow frontend. Verify generated sources with `python scripts/generate_antlr.py --check` and run official parity evidence with `python -m findsl.cli official-frontend-evidence ...`. See `docs/37_ANTLR影子前端与迁移证据.md` for commands and interpretation boundaries.

The official compiler now exposes an immutable Typed AST and a SQL-free logical IR shadow pipeline. `python -m findsl.cli official-slot-ir ... --json` shows function-slot bindings, explicit types, validated logical operators, and a deterministic content-derived plan ID without changing the existing SQL compiler. On the current official workbook, 5,695 strict inputs produce Typed ASTs and 2,034 produce validated logical plans; the separate grounded strict SQL baseline remains 1,097. See `docs/38_Typed_AST与Logical_IR实现说明.md` and `reports/phase3_official_ir_evidence.md` for the evidence boundary.

Phase 4 adds a schema-validated official indicator registry, domain binding, SQL-free financial-domain nodes, and a deterministic rule optimizer. The registry distinguishes 197 provided/derived static indicators from workbook indicators whose required data domains are absent, so missing financial/fund/index data reports `DOMAIN_DATA_UNAVAILABLE` instead of becoming fake SQL. `official-slot-optimize` exposes the domain requirements and rewrite trace; `official-domain-evidence` audits all 5,799 official rows. See `docs/39_领域IR注册表与规则优化器说明.md`.

Phase 5 adds a schema-validated physical catalog, bounded Doris candidate planner, validated Physical IR, and a SQLGlot-only Doris AST backend. The shadow backend currently produces 33 grounded plans on the 5,799 official rows; all 33 preserve supported market/latest-date constraints, round-trip in the Doris dialect, and pass the SELECT safety lint. On real Apache Doris data, 30 deterministic candidates match the legacy compiler exactly by row count and streaming SHA-256 (`30/30`, zero execution errors); three top-level LIMIT queries without ORDER BY are recorded as `NONDETERMINISTIC_LIMIT` and excluded rather than being counted as passes. Direct numeric rank uses a `ROW_NUMBER()` window partitioned by trading date, a stable `tgtcode` tie-breaker, and an outer rank filter. Catalog-declared anchor resources preserve the basic-market universe for extension, security, and technical tables. Missing domains, derived expressions without controlled strategies, unsupported constraints, and approximate comparisons without catalog tolerances remain explicit failures rather than fake SQL. Use `official-slot-physical`, `official-slot-backend`, and `official-backend-evidence`; see `docs/40_Doris物理规划与SQL_AST后端说明.md`.

Phase 6A replaces the shadow planner's fixed priority cost with a versioned Doris statistics snapshot. `official-physical-stats` collects real row counts, stored sizes, and the FE version through controlled metadata commands; the snapshot is bound to the physical catalog fingerprint. Complete statistics produce an auditable primary-plus-anchor scan-byte cost with `estimated=false`, while missing statistics fall back explicitly to catalog priority. The model does not invent selectivity or equate stored bytes with latency. Prefix and hot-materialization alternatives will enter the same interface as multiple candidates in Phase 6B.

Phase 6B adds 14 schema-validated prefix-average strategies for fixed moving-price and moving-volume averages. The planner now enumerates direct materialized columns and controlled prefix-difference expressions, records both decisions, and keeps uncalibrated alternatives in `shadow` mode. SQLGlot renders the prefix path from typed AST nodes using current/previous prefix rows; no legacy SQL fragments enter the backend. Real Doris evidence matches both representative result sets exactly (`2/2`, zero errors), but the correlated prefix path is currently slower than the technical feature table (`0.795x` and `0.734x` legacy-over-prefix ratios in the implementation-bound run), so the default remains `direct_column`. Use `official-prefix-evidence` to reproduce the result hashes and timing before changing any strategy to `active`.

Phase 7 exposes the ANTLR-to-SQLGlot path through one `compile_official` orchestration service and a dedicated `/api/official/analyze` Demo endpoint. The endpoint never silently falls back to the legacy compiler: unsupported data domains, constraints, expressions, or physical mappings return the exact terminal stage, stable code, partial IR evidence, and candidate decisions. Versioned official-slot examples are available from `/api/official/examples`. The migration funnel measures the new backend against the 1,097-query legacy strict success set; the current result is `33/1,097` (`3.01%`), with the largest actionable gaps classified as physical constraints, mappings, domain capabilities, and expressions. See `reports/phase7_official_pipeline_funnel.md`; this migration percentage is not presented as SQL correctness.

Phase 8 replaces 20 high-frequency legacy SQL expression strings with a closed, recursively type-checked physical expression algebra. Configuration may declare only typed columns, literals, arithmetic, explicit safe division, comparisons, boolean composition, negation, and coalesce; arbitrary SQL text and function escape hatches are rejected. The planner lowers these declarations into Physical IR and SQLGlot nodes, with explicit parentheses preserving arithmetic tree semantics and `NULLIF(denominator, 0)` protecting ratio formulas. Official migration coverage rises from `33/1,097` to `72/1,097` (`6.56%`) while compile P95 remains `5.2387 ms`. Six representative newly eligible strategies match the legacy backend on real Doris data by row count and SHA-256 (`6/6`, zero errors); their shadow P95 is `1,025.2171 ms`, below the 10-second execution target but slower than the legacy comparison path, so Phase 8 claims correctness expansion rather than speedup. See `reports/phase8_derived_expression_funnel.md` and `reports/phase8_derived_expression_doris.md`.

If running from the repository root without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
python -m findsl.cli compile 'filter(RET(indicator("close"), 2) > 0.05)'
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)'
python -m findsl.cli suggest-dsl '今日收盘价创二百五十日新高'
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --json
python -m findsl.cli llm-suggest-dsl '近3日成交量累计大于300' --model '<provider-model>' --json
python -m findsl.cli official-suite --json
python -m findsl.cli official-slot-coverage --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/official_slot_coverage.json --report-output reports/official_slot_coverage.md
python -m findsl.cli official-coverage-funnel --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/phase7_official_pipeline_funnel.json --report-output reports/phase7_official_pipeline_funnel.md
python -m findsl.cli official-performance-matrix --json
python -m findsl.cli defense-package --json
powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reference_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify_sql_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\official_suite.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\validate_llm_candidates.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\defense_package.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_prefix_sum.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\scale_benchmark.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_doris_scale_evidence.ps1 -ProxyUrl "http://127.0.0.1:7897"
python .\scripts\fetch_real_market_sample.py
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
```

## Semantic Reference Evaluation

The repository includes a small sample A-share-style dataset under `data/samples/`.
`PandasReferenceEvaluator` interprets DSL directly over those CSV tables. It is intentionally independent from the SQL generator, so it can serve as a slow but trustworthy semantic oracle.

This is the foundation for later SQL equivalence tests:

```text
DSL -> Pandas reference result
DSL -> compiler -> SQLite/Doris SQL result
compare result sets
```

The current implementation already runs the generated SQL over in-memory SQLite tables loaded from CSV fixtures. SQLite is used as a lightweight local execution harness, while the generated SQL remains Doris-oriented and window-safe. This gives every compiler change a fast semantic regression gate before the Doris execution path is introduced.

## Real Market Sample

`scripts/fetch_real_market_sample.py` produces a small, versioned Eastmoney A-share sample in `data/real_samples/eastmoney_a_share_sample/`. The sample includes `daily_quote.csv`, `stock_universe.csv`, cached raw JSON payloads, metadata, and ready-to-run DSL cases for turnover, return rate, and rolling volume. `money_flow.csv` is a neutral zero-valued placeholder only so the existing three-table sample loader can run quote-only DSLs; it is not used as real money-flow evidence.

Use the sample for business credibility in the demo:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample
```

Refresh the raw Eastmoney JSON only when needed:

```powershell
python .\scripts\fetch_real_market_sample.py --refresh --proxy "http://127.0.0.1:7897"
```

## Prefix-Sum Optimization

Indicators can declare prefix-sum support in `configs/indicators.json`. When the compiler sees an eligible `SUM(indicator(...), window)` expression, it rewrites the rolling window aggregate into prefix table joins:

```text
window_sum = current_prefix - prefix_at_row_no_minus_window
```

This is the optimizer path aimed at the competition's long-range query acceleration requirement. Unsupported indicators still use ordinary SQL window functions, so the optimization is safe and configuration-driven. For sparse auxiliary sources, generated prefix tables are built from the daily quote trading calendar with a left join back to the auxiliary values, preserving the same stock-date universe used by the reference oracle.

The `benchmark-prefix-sum` command compiles the same DSL twice: once with prefix-sum disabled as a baseline window query, and once with prefix-sum enabled. It then checks both SQL outputs against the Pandas reference result and writes a Markdown report with timing and plan-shape evidence. Local SQLite timings are treated as regression signals; the competition-scale acceleration claim is backed separately by Doris data, `EXPLAIN`, row-count parity, and latency evidence.

`scripts/scale_benchmark.ps1` goes one step further: it generates deterministic synthetic market data under `data/generated/scale/`, runs a 120-day rolling `SUM` query against baseline-window and prefix-sum SQL, and writes `reports/prefix_sum_scale_benchmark.md`. The report records correctness gates, local timing, plan shape, and a long-window feature-access reduction estimate. It is designed as reproducible pre-Doris evidence and complements, rather than replaces, the committed Doris cluster proof.

After the Doris schema, data, and prefix tables are loaded, `scripts/collect_doris_evidence.ps1` captures real-cluster `EXPLAIN`, repeated `COUNT(*)` latency, row-count equivalence, plan-shape markers, and the default 10x speedup target into `reports/doris_cluster_evidence.md` plus a JSON sidecar. The readiness report consumes this file and closes the `Doris-scale performance proof` warning only when baseline and optimized SQL both succeed, row counts match, the baseline contains a window plan, the optimized query uses a prefix table, and measured Doris speedup meets the 10x target.

For the repeatable local 5M-row path, `scripts/prepare_doris_scale_evidence.ps1` starts the Docker Doris cluster, generates deterministic CSV data, Stream Loads the base tables, rebuilds prefix tables, collects Doris evidence, and reruns readiness. Use `-ProxyUrl "http://127.0.0.1:7897"` when Docker image pulls need the local VPN proxy.

## Structured Explain

Compiler JSON output includes both human-readable `trace` text and machine-readable `explain` steps. Each explain step records a rule name, status, message, and evidence dictionary. This lets evaluation reports, future UI panels, and answer-defense materials show why an optimization was applied or skipped.

## Web Demo

`scripts/serve_demo.ps1` starts a local Web Demo at `http://127.0.0.1:8765`. The demo lets judges or teammates enter an official-style Chinese stock-screening request, review compiler-validated DSL candidates, choose baseline cases, official-style positive/negative presets, or the Eastmoney real-market quote sample, run the deterministic compiler, inspect Doris SQL, AST, optimizer explain, and SQL/reference verification rows, and receive repair hints when invalid DSL is submitted. Negative presets show the expected and actual diagnostic code, making error recovery a live demonstration instead of a hidden test report. Real-market presets are routed through a small whitelisted dataset so the live page can show true A-share codes and dates without mixing that business sample into the 5M-row Doris performance claim.

The same server exposes JSON APIs:

- `GET /api/examples`
- `POST /api/suggest`
- `POST /api/analyze`
- `GET /api/official/examples`
- `POST /api/official/analyze`

The first three endpoints preserve the original internal FinDSL demonstration and its local reference verifier. The `/api/official/*` endpoints use the official seven-slot syntax and the new ANTLR/Typed AST/Logical IR/Physical IR/SQLGlot pipeline. They are intentionally separate until the migration funnel shows that replacing the legacy path will not regress supported official behavior.

## Safe LLM Candidate Adapter

`validate-llm-candidates` is an offline safety adapter for model-proposed DSL. It accepts a structured or markdown-style LLM response file, extracts candidate FinDSL expressions, rejects direct SQL-looking output, compiles remaining DSL through the deterministic compiler, and requires SQL/reference equivalence when verification is enabled.

The bundled `data/samples/llm_candidate_response.json` intentionally contains one valid DSL candidate, one misspelled indicator, and one unsafe direct SQL candidate. This gives the defense package concrete evidence that LLM assistance is useful but cannot bypass parser, semantic validation, diagnostics, optimizer explain, or reference-oracle checks.

`llm-suggest-dsl` adds a real-provider entry point without changing that boundary. It posts a JSON-only FinDSL prompt to an OpenAI-compatible `/chat/completions` endpoint, extracts candidates from the response, and immediately reuses `validate_llm_candidates`. The command reads `FINDSL_LLM_MODEL` or `--model`, `FINDSL_LLM_API_KEY` by default, and optionally `FINDSL_LLM_BASE_URL` for local or domestic-compatible providers:

```powershell
$env:FINDSL_LLM_API_KEY="<your key>"
$env:FINDSL_LLM_MODEL="<provider-model>"
$env:FINDSL_LLM_BASE_URL="https://api.openai.com/v1"
python -m findsl.cli llm-suggest-dsl "近3日成交量累计大于300" --json
```

For a local provider that does not require authentication, pass `--no-api-key --base-url http://127.0.0.1:8000/v1 --model <local-model>`. Provider access is optional; the offline adapter and deterministic NL2DSL templates remain the reproducible competition path.

## Doris Assets

`scripts/generate_doris_assets.ps1` creates the SQL files under `deploy/doris/`:

```text
01_schema.sql
02_sample_data.sql
03_build_prefix_tables.sql
04_smoke_queries.sql
```

These files are a smoke-test deployment path for Doris. The schema generator emits monthly `trade_date` auto partitions plus a shared `colocate_with` group on `ts_code`, so the date-range pushdown and prefix-table joins have visible physical-design support. See `docs/doris_runbook.md` for execution order and production notes.

To capture cluster evidence for the submission gate:

```powershell
$env:DORIS_HOST="127.0.0.1"
$env:DORIS_PORT="9030"
$env:DORIS_USER="root"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

The script defaults `DORIS_EVIDENCE_MIN_SPEEDUP` to `10.0`, matching the competition acceleration target. Keep the default for final submission evidence so `submission_readiness.ps1` can validate the 10x marker.

For password-protected private clusters, set `DORIS_PASSWORD` and `DORIS_PASSWORD_MODE=inline`, or use `DORIS_PASSWORD_MODE=prompt` in an interactive shell. The generated report redacts inline passwords from the command template.

## Submission Readiness

`scripts/submission_readiness.ps1` generates `reports/submission_readiness.md` and companion evidence reports. The readiness report is designed as a pre-submission gate: it runs pytest, compiler evaluation, SQL/reference equivalence, prefix-sum benchmark checks, Demo API smoke checks, NL2DSL validated-candidate checks, structured diagnostics checks, Doris SQL validation evidence, public real-market sample verification, config-only indicator extension evidence, Doris asset integrity checks, Doris cluster evidence marker checks, and git rollback-state inspection.

The readiness report also runs `official-suite`, which currently covers 37 positive official-style cases and 37 negative diagnostic cases across staged filters, top-N ranking, percent-cutoff ranking, date-range pushdown, window-safe date pruning, rolling boolean conditions, moving averages, rolling extrema, prefix-sum aggregates, hot-window materialized columns, market joins, cross-market boolean `&/^/|` logic, arithmetic predicates, signed numeric thresholds, sparse auxiliary joins, repeated rank stages, case-insensitive inputs, inequality predicates, parenthesized OR predicates, return-rate drawdown thresholds, duplicate named arguments, invalid dates, invalid rank directions, invalid windows, mutually exclusive rank cutoffs, and invalid-DSL repair diagnostics. Each positive case must compile, expose expected SQL/trace/explain evidence, and match the independent SQL/reference result. Each negative case must fail with a stable diagnostic code and actionable suggestions.

It also validates the safe LLM candidate loop and generates `reports/defense_package.md`, a live-defense walkthrough that maps NL2DSL validation, official NL2DSL template coverage, LLM guardrails, the OpenAI-compatible provider contract, prefix-sum positive presets, diagnostic negative presets, public real-market quote samples, official coverage, compiler latency, Doris asset integrity, and the exported Doris proof to concrete scoring evidence.

Required gates fail the command when correctness or asset integrity breaks. Warning gates highlight competition risks such as missing Doris-cluster scale proof or uncommitted local changes.

Because `reports/` is generated and ignored by Git, run `scripts/export_submission_artifacts.ps1` before the final commit. It copies lightweight evidence reports into `submission_artifacts/evidence_snapshots/` so the submitted repository contains a reviewable evidence snapshot without committing large CSV data.

The same export step also writes `submission_artifacts/evidence_metadata.json`, a machine-readable summary of readiness gates, pytest count, official-suite counts, and Doris cluster speedup. It also renders `submission_artifacts/evidence_summary.md`, a short human-readable evidence page for reviewers. Treat both files as consistency indexes for reports, PPT, and Demo indicators; the original snapshot files remain the audit source.

## Competition-Oriented Design

This repository is built around the topic's quantitative requirements:

- SQL correctness target: `>= 95%`
- Compile P95 target: `< 50ms`
- Long-range acceleration target: `10x+`
- New indicator/function target: core compiler code change `0 lines`

The current implementation establishes a reliable compiler kernel, correctness oracle, optimizer evidence, Doris assets, real Doris-cluster execution proof, a public real-market quote sample, NL2DSL templates, safe LLM candidate validation, an optional OpenAI-compatible provider entry point, official-style coverage evidence, and a local demo. Provider output is still treated as untrusted DSL-candidate text, so it cannot bypass compiler validation or SQL/reference equivalence.
