param(
  [string]$OfficialWorkbook = $env:FINDSL_OFFICIAL_WORKBOOK,
  [string]$OfficialDataRoot = $env:FINDSL_OFFICIAL_DATA_ROOT,
  [string]$DorisHost = "127.0.0.1",
  [int]$DorisPort = 9030,
  [int]$DorisHttpPort = 8030,
  [string]$DorisUser = "root",
  [string]$DorisDatabase = "newzl",
  [string]$MysqlClient = "mysql"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Invoke-Step {
  param([string]$Name, [scriptblock]$Action)
  Write-Host ""
  Write-Host "==> $Name" -ForegroundColor Cyan
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

if (-not $OfficialWorkbook) {
  throw "Set FINDSL_OFFICIAL_WORKBOOK or pass -OfficialWorkbook."
}
if (-not (Test-Path -LiteralPath $OfficialWorkbook -PathType Leaf)) {
  throw "Official workbook not found: $OfficialWorkbook"
}
if (-not $OfficialDataRoot) {
  throw "Set FINDSL_OFFICIAL_DATA_ROOT or pass -OfficialDataRoot."
}
if (-not (Test-Path -LiteralPath $OfficialDataRoot -PathType Container)) {
  throw "Official data root not found: $OfficialDataRoot"
}

$dirty = (& git status --short --untracked-files=no) -join "`n"
if ($dirty) {
  throw "Commit tracked changes before final evidence collection:`n$dirty"
}
$head = (& git rev-parse HEAD).Trim()
New-Item -ItemType Directory -Force -Path reports | Out-Null
if (-not $env:FINDSL_DORIS_PASSWORD -and $env:DORIS_PASSWORD) {
  $env:FINDSL_DORIS_PASSWORD = $env:DORIS_PASSWORD
}
if (-not $env:DORIS_PASSWORD -and $env:FINDSL_DORIS_PASSWORD) {
  $env:DORIS_PASSWORD = $env:FINDSL_DORIS_PASSWORD
}

Invoke-Step "Source quality gates" {
  python scripts/run_final_quality_gates.py
}
Invoke-Step "Official recovery coverage" {
  python -m findsl.cli official-slot-coverage `
    --workbook $OfficialWorkbook `
    --mode recovery `
    --json-output reports/official_slot_coverage.json `
    --report-output reports/official_slot_coverage.md
}
Invoke-Step "Canonical compiler funnel" {
  python -m findsl.cli official-coverage-funnel `
    --workbook $OfficialWorkbook `
    --json-output reports/official_compiler_funnel.json `
    --report-output reports/official_compiler_funnel.md
}
Invoke-Step "Corpus root-cause audit" {
  python scripts/audit_official_corpus.py `
    --funnel reports/official_compiler_funnel.json `
    --profile enriched_public `
    --output-json reports/official_corpus_root_cause_audit.json `
    --output-md reports/official_corpus_root_cause_audit.md
}
Invoke-Step "Official Doris deployment evidence" {
  powershell -ExecutionPolicy Bypass -File scripts/prepare_official_doris_evidence.ps1 `
    -OfficialRoot $OfficialDataRoot `
    -DorisHost $DorisHost `
    -QueryPort $DorisPort `
    -HttpPort $DorisHttpPort `
    -User $DorisUser `
    -Password $env:DORIS_PASSWORD `
    -Client $MysqlClient `
    -SkipDockerStart `
    -SkipStreamLoad `
    -SkipFeatureTables
}
Invoke-Step "Official materialization watermark" {
  python scripts/check_official_watermarks.py `
    --host $DorisHost --port $DorisPort --user $DorisUser `
    --database $DorisDatabase --client $MysqlClient
}
Invoke-Step "Independent SQL correctness benchmark" {
  python scripts/run_official_correctness_benchmark.py `
    --host $DorisHost --port $DorisPort --user $DorisUser `
    --database $DorisDatabase --client $MysqlClient `
    --skip-watermark-check
}
Invoke-Step "Stratified Doris execution matrix" {
  python scripts/run_official_full_performance_matrix.py `
    --host $DorisHost --port $DorisPort --user $DorisUser `
    --database $DorisDatabase --mysql $MysqlClient `
    --skip-watermark-check --warmups 1 --repeats 7
}
Invoke-Step "Canonical compile latency" {
  python scripts/run_official_compile_latency_benchmark.py --repeats 30
}
$longArgs = @(
  "scripts/run_official_long_horizon_matrix.py",
  "--host", $DorisHost,
  "--port", [string]$DorisPort,
  "--http-port", [string]$DorisHttpPort,
  "--user", $DorisUser,
  "--warmups", "1",
  "--repeats", "5"
)
if ($env:DORIS_PASSWORD) {
  $longArgs += @("--password", $env:DORIS_PASSWORD)
}
Invoke-Step "Five-workload long-horizon matrix" {
  & python @longArgs
}
Invoke-Step "Twelve-function capability matrix" {
  python scripts/generate_capability_matrix.py
}
Invoke-Step "Blind config-only extension" {
  python scripts/generate_blind_extension_evidence.py `
    --json-output reports/blind_extension_evidence.json `
    --report-output reports/blind_extension_evidence.md
}
Invoke-Step "Hero query differential" {
  python scripts/run_hero_query.py --execute-doris `
    --host $DorisHost --port $DorisPort --user $DorisUser `
    --database $DorisDatabase --client $MysqlClient --timeout 30
}
$groupArgs = @(
  "scripts/collect_group_entity_doris_evidence.py",
  "--repo-root", $repoRoot,
  "--host", $DorisHost,
  "--port", [string]$DorisPort,
  "--user", $DorisUser,
  "--database", $DorisDatabase,
  "--json-output", "reports/group_entity_doris.json",
  "--report-output", "reports/group_entity_doris.md"
)
if ($env:DORIS_PASSWORD) {
  $groupArgs += @("--password", $env:DORIS_PASSWORD)
}
Invoke-Step "Group semantics differential" {
  & python @groupArgs
}
Invoke-Step "Final submission metadata" {
  python scripts/build_final_submission_metadata.py --expected-git-head $head
}

Write-Host ""
Write-Host "Final evidence PASS at Git HEAD $head" -ForegroundColor Green
