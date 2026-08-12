# Evidence Snapshot Manifest

- Git HEAD at export: 414a980
- Dataset date range: 2006-01-04 to 2026-04-14
- Snapshot directory: `submission_artifacts/evidence_snapshots`
- Selection policy: current scoring contract, current correctness/performance/Doris evidence, current data-gap audit, and test-required Phase 48 audit inputs only

## Included Evidence Groups

- Readiness and official positive/negative suite
- Official slot coverage and canonical compiler funnel
- Independent SQL correctness benchmark
- Official full performance matrix and 20-year long-horizon benchmark
- Official Doris load, watermark, prefix, adjustment and external catalog evidence
- Current performance taxonomy
- Current official gap taxonomy, external-data inventory and scope-gap audit
- Current Phase 48 scope-policy audit and Phase 6C set-prefix measurement

## Excluded By Design

- Historical phase reports and superseded evidence snapshots: available from Git history.
- `reports/`: locally reproducible working output.
- Doris runtime volumes and generated large CSV files: environment state, not source code.
- PPT, DOCX, PDF, screenshots and videos: generated once after final feature and evidence freeze.
