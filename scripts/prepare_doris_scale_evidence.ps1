param(
  [string]$DorisHost = "127.0.0.1",
  [int]$QueryPort = 9030,
  [int]$HttpPort = 8030,
  [string]$User = "root",
  [string]$Password = "",
  [string]$Database = "findsl_demo",
  [string]$Client = "mysql",
  [string]$ComposeFile = "deploy/doris/docker-compose.quickstart.yaml",
  [string]$DataDir = "data/generated/doris_5m",
  [int]$Stocks = 2000,
  [int]$Days = 2500,
  [string]$StartDate = "2022-01-01",
  [int]$Seed = 2026,
  [int]$Iterations = 5,
  [double]$MinSpeedup = 10.0,
  [string]$Dsl = 'filter(SUM(indicator("volume"), 120) > 1000000)',
  [string]$EvidenceOutput = "reports/doris_cluster_evidence.md",
  [string]$ReadinessOutput = "reports/submission_readiness.md",
  [string]$ProxyUrl = "",
  [switch]$SkipDockerStart,
  [switch]$SkipDataGeneration,
  [switch]$SkipStreamLoad,
  [switch]$SkipReadiness
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-DorisSql {
  param([string]$Sql)

  $mysqlArgs = @(
    "-h", $DorisHost,
    "-P", [string]$QueryPort,
    "-u", $User,
    "--connect-timeout", "10",
    "--batch",
    "--raw",
    "-e", $Sql
  )
  if ($Password) {
    $mysqlArgs = @(
      "-h", $DorisHost,
      "-P", [string]$QueryPort,
      "-u", $User,
      "-p$Password",
      "--connect-timeout", "10",
      "--batch",
      "--raw",
      "-e", $Sql
    )
  }
  & $Client @mysqlArgs
}

function Wait-DorisReady {
  $deadline = (Get-Date).AddMinutes(8)
  $lastError = $null
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-DorisSql -Sql "SELECT 1;" | Out-Null
      return
    } catch {
      $lastError = $_
      Start-Sleep -Seconds 5
    }
  }
  throw "Doris query port did not become ready before timeout. Last error: $lastError"
}

function Invoke-StreamLoad {
  param(
    [string]$Table,
    [string]$CsvPath
  )

  if (-not (Test-Path $CsvPath)) {
    throw "CSV file not found: $CsvPath"
  }

  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if (-not $curl) {
    throw "curl.exe is required for Doris Stream Load."
  }

  $label = "findsl_${Table}_$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss'))"
  $url = "http://${DorisHost}:${HttpPort}/api/${Database}/${Table}/_stream_load"
  $auth = "${User}:${Password}"
  $args = @(
    "--fail-with-body",
    "--show-error",
    "--silent",
    "--location-trusted",
    "-u", $auth,
    "-T", $CsvPath,
    "-H", "label: $label",
    "-H", "format: csv",
    "-H", "column_separator:,",
    "-H", "skip_lines:1",
    "-H", "strict_mode:false",
    $url
  )

  $response = & $curl.Source @args
  if ($LASTEXITCODE -ne 0) {
    throw "Stream Load failed for $Table with curl exit code $LASTEXITCODE. Response: $response"
  }

  try {
    $payload = $response | ConvertFrom-Json
  } catch {
    throw "Stream Load returned non-JSON response for ${Table}: $response"
  }

  if ($payload.Status -notin @("Success", "Publish Timeout")) {
    throw "Stream Load failed for $Table. Status=$($payload.Status), Message=$($payload.Message)"
  }

  Write-Host "Loaded ${Table}: Status=$($payload.Status), NumberTotalRows=$($payload.NumberTotalRows), NumberLoadedRows=$($payload.NumberLoadedRows)"
}

if ($ProxyUrl) {
  $env:HTTP_PROXY = $ProxyUrl
  $env:HTTPS_PROXY = $ProxyUrl
}

Write-Step "Checking local tools"
& python --version
& $Client --version
& docker --version

if (-not $SkipDockerStart) {
  Write-Step "Starting local Doris Docker cluster"
  docker compose -f $ComposeFile up -d
}

Write-Step "Waiting for Doris query port"
Wait-DorisReady

if (-not $SkipDataGeneration) {
  Write-Step "Generating deterministic ${Stocks}x${Days} scale CSV data"
  python -m findsl.cli generate-synthetic-data `
    --output-dir $DataDir `
    --stocks $Stocks `
    --days $Days `
    --start-date $StartDate `
    --seed $Seed
}

Write-Step "Regenerating Doris schema and smoke SQL assets"
python -m findsl.cli emit-doris-assets `
  --data-dir data/samples `
  --output-dir deploy/doris `
  --database $Database `
  --buckets 8 `
  --replication-num 1

Write-Step "Applying Doris schema"
$schemaSql = Get-Content -Raw -Path "deploy/doris/01_schema.sql"
Invoke-DorisSql -Sql $schemaSql

if (-not $SkipStreamLoad) {
  Write-Step "Truncating base and prefix tables before scale load"
  Invoke-DorisSql -Sql "USE $Database; TRUNCATE TABLE dwd_stock_daily_quote; TRUNCATE TABLE dwd_stock_money_flow; TRUNCATE TABLE dim_stock_universe; TRUNCATE TABLE dwd_stock_daily_quote_prefix; TRUNCATE TABLE dwd_stock_money_flow_prefix;"

  Write-Step "Stream Loading scale CSV files"
  Invoke-StreamLoad -Table "dwd_stock_daily_quote" -CsvPath (Join-Path $DataDir "daily_quote.csv")
  Invoke-StreamLoad -Table "dwd_stock_money_flow" -CsvPath (Join-Path $DataDir "money_flow.csv")
  Invoke-StreamLoad -Table "dim_stock_universe" -CsvPath (Join-Path $DataDir "stock_universe.csv")
}

Write-Step "Rebuilding prefix tables"
$prefixSql = Get-Content -Raw -Path "deploy/doris/03_build_prefix_tables.sql"
Invoke-DorisSql -Sql $prefixSql

Write-Step "Collecting Doris EXPLAIN and latency evidence"
$env:DORIS_HOST = $DorisHost
$env:DORIS_PORT = [string]$QueryPort
$env:DORIS_USER = $User
$env:DORIS_DATABASE = $Database
$env:DORIS_CLIENT = $Client
$env:DORIS_EVIDENCE_ITERATIONS = [string]$Iterations
$env:DORIS_EVIDENCE_MIN_SPEEDUP = [string]$MinSpeedup
$env:DORIS_EVIDENCE_DSL = $Dsl
$env:DORIS_EVIDENCE_OUTPUT = $EvidenceOutput
if ($Password) {
  $env:DORIS_PASSWORD = $Password
  $env:DORIS_PASSWORD_MODE = "inline"
} else {
  Remove-Item Env:\DORIS_PASSWORD -ErrorAction SilentlyContinue
  $env:DORIS_PASSWORD_MODE = "none"
}
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1

if (-not $SkipReadiness) {
  Write-Step "Running submission readiness report"
  powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
}

Write-Step "Done"
Write-Host "Evidence report: $EvidenceOutput"
if (-not $SkipReadiness) {
  Write-Host "Readiness report: $ReadinessOutput"
}
