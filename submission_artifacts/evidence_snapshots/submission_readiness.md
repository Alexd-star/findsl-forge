# FinDSL Forge Submission Readiness Report

## Decision Summary

- Generated at: 2026-06-07T08:08:11+00:00
- Repository root: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge`
- Git HEAD at report generation: `1456e66` fix: align reference null ranking semantics
- Git branch: `main`
- Blocking gates passed: True
- Warning count: 0

## Gate Matrix

| Gate | Level | Status | Evidence |
|---|---|---|---|
| Pytest regression suite | required | PASS | exit 0, elapsed 14195.1 ms |
| Compiler accuracy and latency | required | PASS | 10/10 cases, fragments 100.00%, P95 2.384 ms |
| SQL/reference equivalence | required | PASS | SQL rows 2, reference rows 2, missing 0, extra 0 |
| Prefix optimizer correctness | required | PASS | matches reference True, matches baseline True |
| Prefix optimizer plan shape | required | PASS | baseline window frames 1, optimized prefix references 4 |
| Demo API smoke | required | PASS | verification True, compile 1.621 ms, rows 2 |
| NL2DSL validated candidate | required | PASS | candidates 1, validated True, verification True, rows 2 |
| LLM candidate safety loop | required | PASS | accepted 1, rejected 2, codes UNKNOWN_INDICATOR, UNSAFE_DIRECT_SQL |
| Structured diagnostics repair hints | required | PASS | diagnostics 1, first code UNKNOWN_INDICATOR, suggestions 2 |
| Doris SQL validation boundary | required | PASS | validation steps 1, issues 0, escaped literal True |
| Real-market quote sample | required | PASS | cases 3/3, raw payloads 2, source Eastmoney public historical K-line endpoint |
| Official-style coverage suite | required | PASS | positive 37/37, negative 37/37 |
| Defense package walkthrough | required | PASS | checks 13/13, report D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\defense_package.md |
| Doris asset integrity | required | PASS | 4/4 generated assets match |
| Long-window scale benchmark evidence | warning | PASS | report exists with correctness markers |
| Git rollback cleanliness | warning | PASS | clean working tree |
| Doris-scale performance proof | warning | PASS | cluster EXPLAIN/latency and 10x speedup evidence captured |

## Competition Metrics

- Compile success rate: 100.00%
- SQL fragment accuracy: 100.00%
- Compile P95 latency: 2.384 ms
- Evaluation cases passed: 10/10
- SQL/reference equivalence: True
- Equivalence SQL rows: 2
- Equivalence reference rows: 2
- Prefix optimized matches reference: True
- Prefix optimized matches baseline: True
- Local SQLite prefix benchmark speedup smoke: 1.11x
- Baseline window frames: 1
- Optimized prefix table references: 4
- Local SQLite timing is not used as the Doris-scale performance claim.
- Demo API smoke: True
- NL2DSL smoke: True
- LLM safety smoke: True
- Diagnostics smoke: True
- Doris SQL validation smoke: True
- Real-market quote sample: True
- Real-market sample cases: 3/3
- Official-style positive cases: 37/37
- Official-style negative diagnostics: 37/37
- Defense package checks: 13/13

## Evidence Artifacts

- Readiness report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\submission_readiness.md`
- Evaluation report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\evaluation_report.md`
- SQL equivalence report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\sql_equivalence_report.md`
- Official-style coverage suite report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\official_suite_report.md`
- Defense package report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\defense_package.md`
- Prefix benchmark report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\prefix_sum_benchmark.md`
- Long-window scale benchmark report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\prefix_sum_scale_benchmark.md`
- Doris cluster evidence report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\doris_cluster_evidence.md`
- Real-market sample report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\real_market_sample_report.md`
- Doris deployment directory: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\deploy\doris`

## Official-Style Coverage Suite

- Suite passed: True
- Positive cases passed: 37/37
- Negative diagnostic cases passed: 37/37
- Report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\official_suite_report.md`

## Defense Package

- Package passed: True
- Checks passed: 13/13
- Report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\defense_package.md`

## Long-Window Scale Evidence

- Scale report exists: True
- Scale report marker check: True
- Scale report bytes: 3037
- Matched markers: Prefix-Sum Scale Benchmark, Optimized matches Pandas reference: True, Optimized matches baseline: True, Long-window feature-access reduction estimate
- Missing markers: <none>

## Doris Cluster Evidence

- Doris cluster report exists: True
- Doris cluster marker check: True
- Doris cluster report bytes: 6947
- Matched markers: Doris Cluster Evidence, Evidence source: Apache Doris MySQL-compatible query port, Evidence passed: True, Baseline success: True, Optimized success: True, Row counts match: True, Minimum Doris speedup target: 10.00x, Doris speedup target met: True, Optimized plan contains prefix table: True, Baseline plan contains window: True
- Missing markers: <none>

## Demo Smoke Test

- Passed: True
- Verification passed: True
- Compile latency: 1.621 ms
- SQL rows: 2
- Error: <none>

## NL2DSL Smoke Test

- Passed: True
- Candidate count: 1
- Top validated: True
- Verification passed: True
- SQL rows: 2
- Top DSL: `then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))`
- Error: <none>

## LLM Candidate Safety Smoke Test

- Passed: True
- Response file: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\data\samples\llm_candidate_response.json`
- Raw candidates: 3
- Accepted candidates: 1
- Rejected candidates: 2
- Accepted candidate verified: True
- Rejected diagnostic codes: UNKNOWN_INDICATOR, UNSAFE_DIRECT_SQL
- Error: <none>

## Diagnostics Smoke Test

- Passed: True
- DSL: `filter(indicator("clos") > 10)`
- Diagnostic count: 1
- First code: UNKNOWN_INDICATOR
- Suggestion count: 2
- Error: <none>

## Doris SQL Validation Smoke Test

- Passed: True
- DSL: `filter(market("A' OR 1=1 --"))`
- Validation explain steps: 1
- Issue count: 0
- Escaped literal: True
- Error: <none>

## Real-Market Quote Sample

- Passed: True
- Data directory: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\data\real_samples\eastmoney_a_share_sample`
- Source: Eastmoney public historical K-line endpoint
- Raw payloads: 2
- Cases passed: 3/3
- SQL rows total: 21
- Missing files: <none>
- Errors: <none>
- Report: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\reports\real_market_sample_report.md`

## Doris Asset Integrity

| File | Exists | Matches generator | Bytes |
|---|---:|---:|---:|
| `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\deploy\doris\01_schema.sql` | True | True | 2268 |
| `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\deploy\doris\02_sample_data.sql` | True | True | 1799 |
| `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\deploy\doris\03_build_prefix_tables.sql` | True | True | 1173 |
| `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\deploy\doris\04_smoke_queries.sql` | True | True | 964 |

## Git Rollback State

- Repository detected: True
- Clean working tree: True
- Dirty entries: none

## Pytest Evidence

- Command: `C:\Program Files\Python39\python.exe -m pytest`
- Exit code: 0
- Elapsed: 14195.1 ms

```text
........................................................................ [ 38%]
........................................................................ [ 76%]
............................................                             [100%]
188 passed in 13.52s
```

## Award-Readiness Differentiators

- Deterministic typed compiler path instead of LLM-only SQL generation.
- Independent Pandas reference oracle plus SQLite SQL execution regression.
- Config-driven indicators and functions for low-cost business expansion, with defense evidence for config-only indicator extension.
- Safe date-range, window-aware upper-bound, and prefix-sum full-range pruning expose partition-pruning-friendly `trade_date` predicates.
- Prefix-sum rewrite path for long rolling windows with baseline/optimized evidence.
- Structured optimizer explain records for defense and UI visualization.
- Local Web Demo/API exposes DSL, AST, SQL, explain, and SQL/reference verification in one workflow.
- Cross-market boolean operators `&`, `^`, and `|` compile through the same typed AST, Doris SQL, and reference-equivalence gates.
- NL2DSL candidate layer turns natural-language requests into compiler-validated DSL rather than free-form SQL.
- Official-style NL2DSL templates cover bottom-rank, percent-rank, high-turnover rank, B-market average-volume threshold, date-window moving-average, signed net-outflow, rolling-min, return-rate, and date-prefix-sum pruning scenarios.
- Optional LLM adapter validates model-proposed DSL, rejects direct SQL, and records diagnostic evidence for unsafe outputs.
- Optional OpenAI-compatible provider path can request JSON DSL candidates while preserving the same deterministic safety loop.
- Doris SQL validation enforces single-query shape, known table references, and no window-in-WHERE leaks.
- SQL string literals are escaped by the compiler before they reach generated Doris SQL.
- Public Eastmoney quote sample proves the same SQL/reference verifier works on real A-share codes and dates without using the tiny sample as performance evidence.
- DSL equality operators are normalized to Doris-compatible SQL comparison operators.
- Structured diagnostics convert invalid DSL into stable error codes and repair hints.
- Semantic hardening rejects hidden-eval style invalid DSL before SQL generation.
- Doris DDL includes trade-date auto partitions and colocated stock-code distribution for pruning and local prefix joins.
- Doris sample data, prefix-table build SQL, and smoke queries are generated from the same registry.

## Remaining High-Value Work

- Re-run Doris-cluster EXPLAIN and latency evidence whenever scale data, table layout, or optimizer rules change.
- Refresh the generated one-minute defense video when screenshots or evidence values change; add human voiceover only if the portal requires narrated media.
- Broaden the DSL corpus with more official-style questions and negative/error cases.
- Use the provider-backed LLM path only with stable credentials, timeout settings, and saved raw responses when preparing live demos.