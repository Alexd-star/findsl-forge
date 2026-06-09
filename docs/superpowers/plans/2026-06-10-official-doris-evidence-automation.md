# Official Doris Evidence Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the official Topic 19 CSV package to generate reproducible Apache Doris row-count, SQL execution, EXPLAIN, and speedup evidence.

**Architecture:** Keep the official-data path separate from the internal demo DSL path. `deploy/doris/official/*.sql` owns Doris schema and feature tables, `scripts/prepare_official_doris_evidence.ps1` owns environment orchestration and evidence collection, and `reports/official_doris_evidence.md/json` records runtime evidence.

**Tech Stack:** PowerShell, Apache Doris Docker quickstart, MySQL client, curl Stream Load, Python pytest, FinDSL official slot compiler.

---

### Task 1: Lock Official CSV Null Handling

**Files:**
- Modify: `deploy/doris/official/01_schema.sql`
- Modify: `deploy/doris/official/02_stream_load.md`
- Modify: `tests/test_official_doris_assets.py`

- [x] **Step 1: Add failing test for nullable official price columns**

```python
assert "lastPx BIGINT,\n  preClosePx BIGINT," in schema
assert "lastPx BIGINT NOT NULL" not in schema
assert "preClosePx BIGINT NOT NULL" not in schema
assert "strict_mode:false" in stream_load
```

- [x] **Step 2: Run the test and confirm it fails before schema correction**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\test_official_doris_assets.py -q
```

Expected before fix: failure on nullable `lastPx/preClosePx` or missing `strict_mode:false`.

- [x] **Step 3: Correct official schema and Stream Load runbook**

Use nullable `BIGINT` for `lastPx` and `preClosePx`. Keep `strict_mode:false` and `max_filter_ratio:0` so official empty numeric cells become `NULL` while any filtered row remains visible.

- [x] **Step 4: Verify full official NOT NULL columns have no empty values**

Run:

```powershell
@'
import csv
from pathlib import Path
root = Path(r'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统')
checks = {
    'stock_code': (root / 'Doris A股行情数据集/股票代码表/hsj_stock_code_info.csv', ['mktcode','tgtcode','name','tztcode','stFlag','ahFlag','hkConnFlag','shConnFlag','szConnFlag','hsFlag','hsjFlag','kcbFlag','gemFlag','bShareFlag']),
    'hq_basic': (root / 'Doris A股行情数据集/行情基本数据宽表/hsj_stock_hq_basic.csv', ['mktcode','tgtcode','bizdate','qfqMulti','qfqAdd','hfqMulti','hfqAdd']),
    'hq_ext': (root / 'Doris A股行情数据集/行情衍生数据/hsj_stock_hq_ext.csv', ['mktcode','tgtcode','bizdate']),
}
for name, (path, cols) in checks.items():
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        indices = {c: header.index(c) for c in cols}
        counts = {c: 0 for c in cols}
        rows = 0
        for row in reader:
            rows += 1
            for c, idx in indices.items():
                if idx >= len(row) or row[idx] == '':
                    counts[c] += 1
    print(name, 'rows=', rows)
    print(counts)
'@ | python -
```

Expected: every listed NOT NULL column has `0` empty values.

### Task 2: Make Stream Load Work Reliably on Windows Docker Desktop

**Files:**
- Modify: `scripts/prepare_official_doris_evidence.ps1`
- Modify: `deploy/doris/official/02_stream_load.md`
- Modify: `tests/test_official_doris_assets.py`

- [x] **Step 1: Add failing test for the local BE Stream Load endpoint**

```python
assert '[int]$StreamLoadPort = 8040' in official_evidence_script
assert 'http://${StreamLoadHost}:${StreamLoadPort}/api/newzl/${Table}/_stream_load' in official_evidence_script
assert '"Expect: 100-continue"' in official_evidence_script
```

- [x] **Step 2: Reproduce Doris protocol failure**

Run a two-line CSV against FE `8030` without the `Expect` header.

Expected: Doris returns `There is no 100-continue header`.

- [x] **Step 3: Prove the corrected endpoint with a tiny CSV**

Run:

```powershell
$mysql='C:\Program Files\MySQL\MySQL Workbench 8.0\mysql.exe'
$tmp = Join-Path $env:TEMP 'findsl_doris_null_probe.csv'
@('id,val','1,','2,123') | Set-Content -LiteralPath $tmp -Encoding ASCII
& $mysql -h 127.0.0.1 -P 9030 -u root -e "CREATE DATABASE IF NOT EXISTS findsl_probe; DROP TABLE IF EXISTS findsl_probe.null_probe; CREATE TABLE findsl_probe.null_probe (id INT NOT NULL, val BIGINT NULL) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 1 PROPERTIES ('replication_num'='1');"
curl.exe --fail-with-body --show-error --silent --location-trusted -u root: -T $tmp -H "Expect: 100-continue" -H "label: findsl_null_probe_$([DateTime]::UtcNow.ToString('yyyyMMddHHmmssfff'))" -H "format: csv" -H "column_separator:," -H "skip_lines:1" -H "strict_mode:false" -H "max_filter_ratio:0" "http://127.0.0.1:8040/api/findsl_probe/null_probe/_stream_load"
& $mysql -h 127.0.0.1 -P 9030 -u root --batch --raw -e "SELECT id, IFNULL(CAST(val AS CHAR), 'NULL') AS val FROM findsl_probe.null_probe ORDER BY id;"
```

Expected: `NumberTotalRows=2`, `NumberLoadedRows=2`, `NumberFilteredRows=0`, and row `1` has `NULL`.

- [x] **Step 4: Fix evidence script**

Use `StreamLoadHost=127.0.0.1`, `StreamLoadPort=8040`, `Expect: 100-continue`, `timeout:7200`, `strict_mode:false`, and `max_filter_ratio:0`.

### Task 3: Run Official Full Evidence

**Files:**
- Read: official CSV package under the Topic 19 directory
- Execute: `scripts/prepare_official_doris_evidence.ps1`
- Generate: `reports/official_doris_evidence.md`
- Generate: `reports/official_doris_evidence.json`

- [x] **Step 1: Start or verify local Doris**

```powershell
docker compose -f deploy/doris/docker-compose.quickstart.yaml up -d
& 'C:\Program Files\MySQL\MySQL Workbench 8.0\mysql.exe' -h 127.0.0.1 -P 9030 -u root -e "SELECT 1 AS ok; SHOW BACKENDS;"
```

Expected: `SHOW BACKENDS` contains `Alive=true`.

- [x] **Step 2: Run full official evidence script**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_official_doris_evidence.ps1 `
  -OfficialRoot "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
```

Expected: script creates official tables, loads all three CSV files, validates exact row counts, builds feature tables, and writes Markdown/JSON evidence.

Actual on 2026-06-10: full Stream Load loaded `5686 / 13650347 / 6170822` rows with `Filtered=0`. Technical feature construction initially hit a single-BE memory limit, then passed after adding `mktcode + tgtcode hash bucket` sharding with `TechnicalBucketCount=16`.

- [x] **Step 3: Check exact row-count parity**

```powershell
& 'C:\Program Files\MySQL\MySQL Workbench 8.0\mysql.exe' -h 127.0.0.1 -P 9030 -u root --batch --raw -e "SELECT 'code' AS table_name, COUNT(*) FROM newzl.hsj_stock_code_info UNION ALL SELECT 'basic', COUNT(*) FROM newzl.hsj_stock_hq_basic UNION ALL SELECT 'ext', COUNT(*) FROM newzl.hsj_stock_hq_ext;"
```

Expected: `5686`, `13650347`, `6170822`.

Actual on 2026-06-10: base tables match exactly, and `hsj_stock_hq_basic_prefix`, `hsj_stock_hq_ext_prefix`, and `hsj_stock_hq_basic_technical` each contain `13650347` rows.

- [x] **Step 4: Check evidence report**

```powershell
Get-Content reports\official_doris_evidence.md -TotalCount 80
Get-Content reports\official_doris_evidence.json -TotalCount 40
```

Expected: report contains row-count parity, date ranges, query evidence, Stream Load responses, SQL, EXPLAIN, and baseline-vs-prefix speedup.

Actual on 2026-06-10: `reports/official_doris_evidence.md/json` contains base row counts, feature row counts, date ranges, SQL/EXPLAIN, baseline/prefix row-count equivalence, and official Doris prefix speedup.

### Task 4: Refresh Official Coverage and Submission Snapshots

**Files:**
- Generate: `reports/official_slot_coverage.md`
- Generate: `reports/official_slot_coverage.json`
- Copy selected evidence to: `submission_artifacts/evidence_snapshots/`
- Modify: `README.md`
- Modify: `docs/21_官方真实数据冲刺计划与验收闭环.md`

- [x] **Step 1: Refresh official workbook coverage**

```powershell
$env:PYTHONPATH='src'
python -m findsl.cli official-slot-coverage `
  --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" `
  --json-output reports\official_slot_coverage.json `
  --report-output reports\official_slot_coverage.md `
  --sample-size 50 `
  --json
```

Expected: parse success remains `5792/5799`; compile success is at least the latest baseline `1682`.

Actual on 2026-06-10: `row_count=5799`, `parse_ok=5792`, `compile_ok=1682`.

- [x] **Step 2: Copy final evidence snapshots after successful full load**

```powershell
New-Item -ItemType Directory -Force submission_artifacts\evidence_snapshots | Out-Null
Copy-Item reports\official_doris_evidence.md submission_artifacts\evidence_snapshots\official_doris_evidence.md -Force
Copy-Item reports\official_doris_evidence.json submission_artifacts\evidence_snapshots\official_doris_evidence.json -Force
Copy-Item reports\official_slot_coverage.md submission_artifacts\evidence_snapshots\official_slot_coverage.md -Force
Copy-Item reports\official_slot_coverage.json submission_artifacts\evidence_snapshots\official_slot_coverage.json -Force
```

Expected: submission snapshots contain real generated reports and are not hand-written placeholders.

Actual on 2026-06-10: `scripts/export_submission_artifacts.ps1` now includes official Doris and official slot coverage snapshots and regenerates `evidence_metadata.json` / `evidence_summary.md`.

- [x] **Step 3: Run complete verification before commit**

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
```

Expected: all tests pass.

Actual on 2026-06-10: full pytest passes with `261 passed`; submission readiness required gates pass, with the only warning being the expected dirty working tree before commit.

- [ ] **Step 4: Commit and push**

```powershell
git add deploy/doris/official/01_schema.sql deploy/doris/official/02_stream_load.md scripts/prepare_official_doris_evidence.ps1 tests/test_official_doris_assets.py docs/21_官方真实数据冲刺计划与验收闭环.md docs/superpowers/plans/2026-06-10-official-doris-evidence-automation.md README.md submission_artifacts/evidence_snapshots
git commit -m "feat: automate official Doris evidence"
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
$env:ALL_PROXY='socks5://127.0.0.1:7897'
git push
```

Expected: branch is synced with `origin/main`.
