证据编号: EV-055
截图名称: README 运行命令截图
生成时间: 2026-06-08T16:40:03+08:00
工作目录: D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge
命令: Select-String -Path .\README.md -Pattern 'Quick Start|python -m findsl.cli|submission_readiness|official-suite|serve-demo' -Context 0,1 | Select-Object -First 90
退出码: 0
耗时: 0.310s
期望退出码: 0
状态: PASS

----- STDOUT -----

> README.md:74:## Quick Start
  README.md:75:
> README.md:78:python -m findsl.cli compile 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))'
> README.md:79:python -m findsl.cli evaluate --input data/samples/queries.jsonl --output reports/evaluation_report.md
> README.md:80:python -m findsl.cli reference 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
> README.md:81:python -m findsl.cli verify-sql 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
> README.md:82:python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json
> README.md:83:python -m findsl.cli verify-sql 'filter(RET(indicator("close"), 2) > 0.05)' --data-dir data/samples --json
> README.md:84:python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_s
ample
> README.md:85:python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json
> README.md:86:python -m findsl.cli suggest-dsl '筛选A股连续三天主力净流入为正并按换手率排名前一百' --data-dir data/samples --json
> README.md:87:python -m findsl.cli suggest-dsl 'A股存在资金流入后按低价取每日2只' --data-dir data/samples --json
> README.md:88:python -m findsl.cli suggest-dsl 'A股每日换手率前50%' --data-dir data/samples --json
> README.md:89:python -m findsl.cli suggest-dsl 'B股近2日均量不低于80' --data-dir data/samples --json
> README.md:90:python -m findsl.cli suggest-dsl '主力净流出低于-1.5' --data-dir data/samples --json
> README.md:91:python -m findsl.cli suggest-dsl 'A股近2日收盘价涨幅超过5%' --data-dir data/samples --json
> README.md:92:python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --text '近3日成交量累计大于300' --data-dir data/samples --json
> README.md:93:python -m findsl.cli llm-suggest-dsl '近3日成交量累计大于300' --model '<provider-model>' --json
> README.md:94:python -m findsl.cli official-suite --output reports/official_suite_report.md --json
> README.md:95:python -m findsl.cli defense-package --output reports/defense_package.md --json
> README.md:96:python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.
md
> README.md:97:python -m findsl.cli scale-benchmark --stocks 300 --days 260 --window 120 --iterations 5 --output reports/prefix_sum_scale_benchmark.md
> README.md:98:python -m findsl.cli collect-doris-evidence --host 127.0.0.1 --port 9030 --user root --database findsl_demo --dsl 'filter(SUM(indicator("volume"), 120) > 1000000)' 
--output reports/doris_cluster_evidence.md
> README.md:99:python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
> README.md:100:python -m findsl.cli readiness-report --output reports/submission_readiness.md
> README.md:101:python -m findsl.cli evidence-metadata --snapshots-dir submission_artifacts/evidence_snapshots --output submission_artifacts/evidence_metadata.json --summary-outpu
t submission_artifacts/evidence_summary.md
  README.md:102:```
> README.md:108:python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
> README.md:109:python -m findsl.cli compile 'filter(RET(indicator("close"), 2) > 0.05)'
> README.md:110:python -m findsl.cli diagnose 'filter(indicator("clos") > 10)'
> README.md:111:python -m findsl.cli suggest-dsl '今日收盘价创二百五十日新高'
> README.md:112:python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --json
> README.md:113:python -m findsl.cli llm-suggest-dsl '近3日成交量累计大于300' --model '<provider-model>' --json
> README.md:114:python -m findsl.cli official-suite --json
> README.md:115:python -m findsl.cli defense-package --json
  README.md:116:powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
> README.md:130:powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
  README.md:131:```
> README.md:156:python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_
sample
  README.md:157:```
> README.md:209:python -m findsl.cli llm-suggest-dsl "近3日成交量累计大于300" --json
  README.md:210:```
> README.md:236:The script defaults `DORIS_EVIDENCE_MIN_SPEEDUP` to `10.0`, matching the competition acceleration target. Keep the default for final submission evidence so `submis
sion_readiness.ps1` can validate the 10x marker.
  README.md:237:
> README.md:242:`scripts/submission_readiness.ps1` generates `reports/submission_readiness.md` and companion evidence reports. The readiness report is designed as a pre-submission
 gate: it runs pytest, compiler evaluation, SQL/reference equivalence, prefix-sum benchmark checks, Demo API smoke checks, NL2DSL validated-candidate checks, structured diagnostic
s checks, Doris SQL validation evidence, public real-market sample verification, config-only indicator extension evidence, Doris asset integrity checks, Doris cluster evidence mar
ker checks, and git rollback-state inspection.
  README.md:243:
> README.md:244:The readiness report also runs `official-suite`, which currently covers 37 positive official-style cases and 37 negative diagnostic cases across staged filters, to
p-N ranking, percent-cutoff ranking, date-range pushdown, window-safe date pruning, rolling boolean conditions, moving averages, rolling extrema, prefix-sum aggregates, hot-window
 materialized columns, market joins, cross-market boolean `&/^/|` logic, arithmetic predicates, signed numeric thresholds, sparse auxiliary joins, repeated rank stages, case-insen
sitive inputs, inequality predicates, parenthesized OR predicates, return-rate drawdown thresholds, duplicate named arguments, invalid dates, invalid rank directions, invalid wind
ows, mutually exclusive rank cutoffs, and invalid-DSL repair diagnostics. Each positive case must compile, expose expected SQL/trace/explain evidence, and match the independent SQ
L/reference result. Each negative case must fail with a stable diagnostic code and actionable suggestions.
  README.md:245:
> README.md:252:The same export step also writes `submission_artifacts/evidence_metadata.json`, a machine-readable summary of readiness gates, pytest count, official-suite counts,
 and Doris cluster speedup. It also renders `submission_artifacts/evidence_summary.md`, a short human-readable evidence page for reviewers. Treat both files as consistency indexes
 for reports, PPT, and Demo indicators; the original snapshot files remain the audit source.
  README.md:253:

----- STDERR -----
<empty>