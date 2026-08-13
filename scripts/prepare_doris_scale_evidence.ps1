param(
  [string]$DorisHost = "127.0.0.1",
  [int]$QueryPort = 9030,
  [int]$HttpPort = 8030,
  [string]$StreamLoadHost = "127.0.0.1",
  [int]$StreamLoadPort = 8040,
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
  [string]$LoadLabelRunId = "v1",
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
  $output = & $Client @mysqlArgs 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Doris SQL failed: $Sql`n$output"
  }
  return ($output | Out-String).Trim()
}

function Get-Scalar([string]$Sql) {
  $text = Invoke-DorisSql -Sql $Sql
  $lines = $text -split "\r?\n" | Where-Object { $_.Trim() }
  return $lines[-1].Trim()
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

  $fileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $CsvPath).Hash.ToLowerInvariant().Substring(0, 16)
  $label = "findsl_${Table}_${fileHash}_${LoadLabelRunId}"
  $url = "http://${StreamLoadHost}:${StreamLoadPort}/api/${Database}/${Table}/_stream_load"
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
    "-H", "strict_mode:true",
    "-H", "max_filter_ratio:0",
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
  if ([int64]$payload.NumberFilteredRows -ne 0) {
    throw "Stream Load filtered rows for ${Table}: $($payload.NumberFilteredRows)"
  }

  Write-Host "Loaded ${Table}: Status=$($payload.Status), NumberTotalRows=$($payload.NumberTotalRows), NumberLoadedRows=$($payload.NumberLoadedRows)"
}

if ($ProxyUrl) {
  $env:HTTP_PROXY = $ProxyUrl
  $env:HTTPS_PROXY = $ProxyUrl
}
$env:NO_PROXY = "127.0.0.1,localhost,172.20.80.0/24"
$env:no_proxy = $env:NO_PROXY

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

$needScaleLoad = -not $SkipStreamLoad
if ($needScaleLoad) {
  $expectedDailyRows = [int64]$Stocks * [int64]$Days
  try {
    $needScaleLoad = -not (
      [int64](Get-Scalar "SELECT COUNT(*) FROM ${Database}.dwd_stock_daily_quote;") -eq $expectedDailyRows -and
      [int64](Get-Scalar "SELECT COUNT(*) FROM ${Database}.dwd_stock_money_flow;") -eq $expectedDailyRows -and
      [int64](Get-Scalar "SELECT COUNT(*) FROM ${Database}.dim_stock_universe;") -eq $Stocks
    )
  } catch {
    $needScaleLoad = $true
  }
}
if ($needScaleLoad) {
  Write-Step "Truncating base and prefix tables before scale load"
  Invoke-DorisSql -Sql "USE $Database; TRUNCATE TABLE dwd_stock_daily_quote; TRUNCATE TABLE dwd_stock_money_flow; TRUNCATE TABLE dim_stock_universe; TRUNCATE TABLE dwd_stock_daily_quote_prefix; TRUNCATE TABLE dwd_stock_money_flow_prefix;"

  Write-Step "Stream Loading scale CSV files"
  Invoke-StreamLoad -Table "dwd_stock_daily_quote" -CsvPath (Join-Path $DataDir "daily_quote.csv")
  Invoke-StreamLoad -Table "dwd_stock_money_flow" -CsvPath (Join-Path $DataDir "money_flow.csv")
  Invoke-StreamLoad -Table "dim_stock_universe" -CsvPath (Join-Path $DataDir "stock_universe.csv")
} else {
  Write-Host "Preserving complete scale tables (explicit skip or idempotent row-count match)"
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
  powershell -ExecutionPolicy Bypass -File .\scripts\refresh_final_evidence.ps1
}

Write-Step "Done"
Write-Host "Evidence report: $EvidenceOutput"
if (-not $SkipReadiness) {
  Write-Host "Readiness report: $ReadinessOutput"
}
