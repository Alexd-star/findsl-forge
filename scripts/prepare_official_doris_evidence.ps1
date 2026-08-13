param(
  [string]$OfficialRoot = $env:FINDSL_OFFICIAL_DATA_ROOT,
  [string]$DorisHost = "127.0.0.1",
  [int]$QueryPort = 9030,
  [int]$HttpPort = 8030,
  [string]$StreamLoadHost = "127.0.0.1",
  [int]$StreamLoadPort = 8040,
  [string]$User = "root",
  [string]$Password = "",
  [string]$Client = "mysql",
  [string]$ComposeFile = "deploy/doris/docker-compose.quickstart.yaml",
  [string]$EvidenceOutput = "reports/official_doris_evidence.md",
  [int]$Iterations = 3,
  [ValidateRange(1, 1024)]
  [int]$TechnicalBucketCount = 16,
  [string]$ProxyUrl = "",
  [string]$LoadLabelRunId = "v1",
  [switch]$SkipDockerStart,
  [switch]$SkipStreamLoad,
  [switch]$SkipFeatureTables
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"

$ExpectedRows = @{
  hsj_stock_code_info = 5686
  hsj_stock_hq_basic = 13650347
  hsj_stock_hq_ext = 6170822
}

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-OfficialFile {
  param([string]$RelativePath)
  $path = Join-Path $OfficialRoot $RelativePath
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Official data file not found: $path"
  }
  return (Resolve-Path -LiteralPath $path).Path
}

function Invoke-DorisSql {
  param([string]$Sql)

  $mysqlArgs = @(
    "-h", $DorisHost,
    "-P", [string]$QueryPort,
    "-u", $User,
    "--connect-timeout", "10",
    "--init-command", "SET enable_sql_cache=false",
    "--batch",
    "--raw",
    "--default-character-set=utf8mb4",
    "-e", $Sql
  )
  if ($Password) {
    $mysqlArgs = @(
      "-h", $DorisHost,
      "-P", [string]$QueryPort,
      "-u", $User,
      "-p$Password",
      "--connect-timeout", "10",
      "--init-command", "SET enable_sql_cache=false",
      "--batch",
      "--raw",
      "--default-character-set=utf8mb4",
      "-e", $Sql
    )
  }
  $output = & $Client @mysqlArgs 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Doris SQL failed: $Sql`n$output"
  }
  return ($output | Out-String).Trim()
}

function Wait-DorisReady {
  $deadline = (Get-Date).AddMinutes(8)
  $lastError = ""
  while ((Get-Date) -lt $deadline) {
    try {
      $backendText = Invoke-DorisSql -Sql "SHOW BACKENDS;"
      if ($backendText -match "\btrue\b") {
        Invoke-DorisSql -Sql "SELECT 1;" | Out-Null
        return
      }
      $lastError = $backendText
    } catch {
      $lastError = $_.Exception.Message
    }
    Start-Sleep -Seconds 5
  }
  throw "Doris backend did not become alive before timeout. Last status: $lastError"
}

function Invoke-StreamLoad {
  param(
    [string]$Table,
    [string]$CsvPath
  )

  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if (-not $curl) {
    throw "curl.exe is required for Doris Stream Load."
  }

  $fileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $CsvPath).Hash.ToLowerInvariant().Substring(0, 16)
  $label = "findsl_official_${Table}_${fileHash}_${LoadLabelRunId}"
  $url = "http://${StreamLoadHost}:${StreamLoadPort}/api/newzl/${Table}/_stream_load"
  $auth = "${User}:${Password}"
  $args = @(
    "--fail-with-body",
    "--show-error",
    "--silent",
    "--location-trusted",
    "-u", $auth,
    "-T", $CsvPath,
    "-H", "Expect: 100-continue",
    "-H", "label: $label",
    "-H", "format: csv",
    "-H", "column_separator:,",
    "-H", "skip_lines:1",
    "-H", "strict_mode:true",
    "-H", "max_filter_ratio:0",
    "-H", "timeout:7200",
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

  Write-Host "Loaded ${Table}: Status=$($payload.Status), Total=$($payload.NumberTotalRows), Loaded=$($payload.NumberLoadedRows), Filtered=$($payload.NumberFilteredRows)"
  return $payload
}

function Get-Scalar {
  param([string]$Sql)
  $text = Invoke-DorisSql -Sql $Sql
  $lines = $text -split "\r?\n" | Where-Object { $_.Trim() }
  return $lines[-1].Trim()
}

function Assert-RowCount {
  param(
    [string]$Table,
    [int]$Expected
  )
  $actual = [int](Get-Scalar -Sql "SELECT COUNT(*) FROM newzl.${Table};")
  if ($actual -ne $Expected) {
    throw "Row count mismatch for ${Table}: expected $Expected, got $actual"
  }
  return $actual
}

function Measure-OfficialQuery {
  param(
    [string]$Name,
    [string]$Sql
  )

  $explain = Invoke-DorisSql -Sql ("EXPLAIN " + $Sql)
  $countSql = "SELECT COUNT(*) FROM ($Sql) evidence_query"
  $durations = @()
  $rowCount = 0
  for ($i = 0; $i -lt $Iterations; $i++) {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $rowCount = [int](Get-Scalar -Sql $countSql)
    $watch.Stop()
    $durations += $watch.Elapsed.TotalMilliseconds
  }
  $avg = ($durations | Measure-Object -Average).Average
  $sorted = $durations | Sort-Object
  $p95Index = [Math]::Min($sorted.Count - 1, [Math]::Ceiling($sorted.Count * 0.95) - 1)
  [pscustomobject]@{
    name = $Name
    sql = $Sql
    explain = $explain
    row_count = $rowCount
    execute_ms = $durations
    avg_ms = [Math]::Round($avg, 3)
    p95_ms = [Math]::Round($sorted[$p95Index], 3)
    plan_contains_prefix = ([string]$explain -match "_(prefix|rollup)" -or $Sql -match "_(prefix|rollup)")
    plan_contains_window = (([string]$explain).ToUpperInvariant() -match "WINDOW" -or $Sql.ToUpperInvariant() -match "ROWS BETWEEN")
  }
}

function Write-EvidenceReport {
  param(
    [array]$Loads,
    [hashtable]$Rows,
    [hashtable]$FeatureRows,
    [string]$BasicDateRange,
    [string]$ExtDateRange,
    [array]$Queries
  )

  if ([System.IO.Path]::IsPathRooted($EvidenceOutput)) {
    $outputPath = $EvidenceOutput
  } else {
    $outputPath = Join-Path (Get-Location) $EvidenceOutput
  }
  $outputDir = Split-Path -Parent $outputPath
  if ($outputDir -and -not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
  }
  $jsonOutputPath = [System.IO.Path]::ChangeExtension($outputPath, ".json")
  $generatedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  $gitHead = (& git rev-parse HEAD).Trim()
  $dorisVersion = (Invoke-DorisSql -Sql "SELECT VERSION();" | Select-Object -Last 1).Trim()
  $optimized = $Queries | Where-Object { $_.name -eq "prefix_optimized_volume_sum_20" } | Select-Object -First 1
  $baseline = $Queries | Where-Object { $_.name -eq "baseline_window_volume_sum_20" } | Select-Object -First 1
  $baselinePrefixRowCountMatch = $false
  if ($baseline -and $optimized) {
    $baselinePrefixRowCountMatch = ($baseline.row_count -eq $optimized.row_count)
    if (-not $baselinePrefixRowCountMatch) {
      throw "Baseline/prefix row-count mismatch: baseline=$($baseline.row_count), prefix=$($optimized.row_count)"
    }
  }
  $speedup = 0.0
  if ($baseline -and $optimized -and $optimized.avg_ms -gt 0) {
    $speedup = [Math]::Round($baseline.avg_ms / $optimized.avg_ms, 3)
  }
  $featureTablesAvailable = $true
  foreach ($featureTable in @("hsj_stock_hq_basic_prefix", "hsj_stock_hq_ext_prefix", "hsj_stock_hq_basic_technical", "hsj_stock_hq_basic_rollup")) {
    if (-not $FeatureRows.ContainsKey($featureTable) -or $FeatureRows[$featureTable] -ne $ExpectedRows["hsj_stock_hq_basic"]) {
      $featureTablesAvailable = $false
    }
  }

  $lines = @(
    "# Official Doris Real-Data Evidence",
    "",
    "## Summary",
    "",
    "- Evidence source: official Topic 19 CSV package",
    "- Generated at: $generatedAt",
    "- Git HEAD: ``$gitHead``",
    "- Doris version: ``$dorisVersion``",
    ("- Doris host: ``{0}``" -f $DorisHost),
    "- Query port: $QueryPort",
    "- FE HTTP port: $HttpPort",
    ("- Stream Load endpoint: ``{0}:{1}``" -f $StreamLoadHost, $StreamLoadPort),
    "- Iterations per query: $Iterations",
    "- Technical feature bucket count: $TechnicalBucketCount",
    "- Official row-count parity: True",
    "- Official feature tables rebuilt in this run: $(-not $SkipFeatureTables)",
    "- Official feature tables available: $featureTablesAvailable",
    "- Baseline/prefix row-count match: $baselinePrefixRowCountMatch",
    "- Baseline vs prefix speedup: ${speedup}x",
    "",
    "## Row Counts",
    "",
    "| Table | Expected | Actual |",
    "|---|---:|---:|"
  )
  foreach ($key in @("hsj_stock_code_info", "hsj_stock_hq_basic", "hsj_stock_hq_ext")) {
    $lines += "| $key | $($ExpectedRows[$key]) | $($Rows[$key]) |"
  }
  $lines += @(
    "",
    "## Feature Table Row Counts",
    "",
    "| Table | Expected | Actual |",
    "|---|---:|---:|"
  )
  foreach ($key in @("hsj_stock_hq_basic_prefix", "hsj_stock_hq_ext_prefix", "hsj_stock_hq_basic_technical", "hsj_stock_hq_basic_rollup")) {
    $lines += "| $key | $($ExpectedRows["hsj_stock_hq_basic"]) | $($FeatureRows[$key]) |"
  }
  $lines += @(
    "",
    "## Date Ranges",
    "",
    '```text',
    $BasicDateRange,
    $ExtDateRange,
    '```',
    "",
    "## Query Evidence",
    "",
    "| Query | Rows | Avg ms | P95 ms | Prefix plan | Window plan |",
    "|---|---:|---:|---:|---:|---:|"
  )
  foreach ($query in $Queries) {
    $lines += "| $($query.name) | $($query.row_count) | $($query.avg_ms) | $($query.p95_ms) | $($query.plan_contains_prefix) | $($query.plan_contains_window) |"
  }
  $lines += @("", "## Stream Load Results", "")
  foreach ($load in $Loads) {
    $lines += '```json'
    $lines += ($load | ConvertTo-Json -Depth 12)
    $lines += '```'
    $lines += ""
  }
  $lines += @("## SQL and EXPLAIN", "")
  foreach ($query in $Queries) {
    $lines += "### $($query.name)"
    $lines += ""
    $lines += '```sql'
    $lines += $query.sql
    $lines += '```'
    $lines += ""
    $lines += '```text'
    $lines += $query.explain
    $lines += '```'
    $lines += ""
  }

  $lines -join "`n" | Set-Content -LiteralPath $outputPath -Encoding UTF8
  [pscustomobject]@{
    schema_version = 1
    generated_at = $generatedAt
    git_head = $gitHead
    doris_version = $dorisVersion
    database = "newzl"
    official_root = Split-Path -Leaf $OfficialRoot
    doris_host = $DorisHost
    query_port = $QueryPort
    fe_http_port = $HttpPort
    stream_load_host = $StreamLoadHost
    stream_load_port = $StreamLoadPort
    row_counts = $Rows
    feature_tables_available = $featureTablesAvailable
    feature_table_row_counts = $FeatureRows
    basic_date_range = $BasicDateRange
    ext_date_range = $ExtDateRange
    baseline_prefix_row_count_match = $baselinePrefixRowCountMatch
    baseline_vs_prefix_speedup = $speedup
    queries = $Queries
    loads = $Loads
  } | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $jsonOutputPath -Encoding UTF8
}

if ($ProxyUrl) {
  $env:HTTP_PROXY = $ProxyUrl
  $env:HTTPS_PROXY = $ProxyUrl
}
$env:NO_PROXY = "127.0.0.1,localhost,172.20.80.0/24"
$env:no_proxy = $env:NO_PROXY

Write-Step "prepare_official_doris_evidence: checking tools and official files"
if (-not $OfficialRoot) {
  throw "Set FINDSL_OFFICIAL_DATA_ROOT or pass -OfficialRoot with the extracted official data directory."
}
$OfficialRoot = [System.IO.Path]::GetFullPath($OfficialRoot)
& python --version
& $Client --version
& docker --version
$codeInfo = Resolve-OfficialFile "Doris A股行情数据集\股票代码表\hsj_stock_code_info.csv"
$hqBasic = Resolve-OfficialFile "Doris A股行情数据集\行情基本数据宽表\hsj_stock_hq_basic.csv"
$hqExt = Resolve-OfficialFile "Doris A股行情数据集\行情衍生数据\hsj_stock_hq_ext.csv"

if (-not $SkipDockerStart) {
  Write-Step "Starting local Doris Docker cluster"
  docker compose -f $ComposeFile up -d
}

Write-Step "Waiting for Doris backend"
Wait-DorisReady

Write-Step "Recreating official newzl tables"
Invoke-DorisSql -Sql "CREATE DATABASE IF NOT EXISTS newzl;"
$needBaseLoad = -not $SkipStreamLoad
if ($needBaseLoad) {
  try {
    $needBaseLoad = -not (
      [int64](Get-Scalar -Sql "SELECT COUNT(*) FROM newzl.hsj_stock_code_info;") -eq $ExpectedRows.hsj_stock_code_info -and
      [int64](Get-Scalar -Sql "SELECT COUNT(*) FROM newzl.hsj_stock_hq_basic;") -eq $ExpectedRows.hsj_stock_hq_basic -and
      [int64](Get-Scalar -Sql "SELECT COUNT(*) FROM newzl.hsj_stock_hq_ext;") -eq $ExpectedRows.hsj_stock_hq_ext
    )
  } catch {
    $needBaseLoad = $true
  }
}
if ($needBaseLoad) {
  Invoke-DorisSql -Sql "DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_rollup; DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_technical; DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_prefix; DROP TABLE IF EXISTS newzl.hsj_stock_hq_ext_prefix; DROP TABLE IF EXISTS newzl.hsj_stock_hq_ext; DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic; DROP TABLE IF EXISTS newzl.hsj_stock_code_info;"
  $schemaSql = Get-Content -Raw -LiteralPath "deploy/doris/official/01_schema.sql"
  Invoke-DorisSql -Sql $schemaSql | Out-Null
} else {
  Write-Host "Preserving complete official base tables (explicit skip or idempotent row-count match)"
  if (-not $SkipFeatureTables) {
    Invoke-DorisSql -Sql "DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_rollup; DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_technical; DROP TABLE IF EXISTS newzl.hsj_stock_hq_basic_prefix; DROP TABLE IF EXISTS newzl.hsj_stock_hq_ext_prefix;"
  } else {
    Write-Host "Preserving existing feature tables because -SkipFeatureTables was set"
  }
}

$loadResults = @()
if ($needBaseLoad) {
  Write-Step "Stream Loading official CSV files"
  $loadResults += Invoke-StreamLoad -Table "hsj_stock_code_info" -CsvPath $codeInfo
  $loadResults += Invoke-StreamLoad -Table "hsj_stock_hq_basic" -CsvPath $hqBasic
  $loadResults += Invoke-StreamLoad -Table "hsj_stock_hq_ext" -CsvPath $hqExt
}

Write-Step "Validating official row counts"
$rows = @{}
$rows["hsj_stock_code_info"] = Assert-RowCount -Table "hsj_stock_code_info" -Expected 5686
$rows["hsj_stock_hq_basic"] = Assert-RowCount -Table "hsj_stock_hq_basic" -Expected 13650347
$rows["hsj_stock_hq_ext"] = Assert-RowCount -Table "hsj_stock_hq_ext" -Expected 6170822
$basicRange = Invoke-DorisSql -Sql "SELECT MIN(bizdate) AS first_basic_date, MAX(bizdate) AS last_basic_date FROM newzl.hsj_stock_hq_basic;"
$extRange = Invoke-DorisSql -Sql "SELECT MIN(bizdate) AS first_ext_date, MAX(bizdate) AS last_ext_date FROM newzl.hsj_stock_hq_ext;"

if (-not $SkipFeatureTables) {
  Write-Step "Building official prefix and technical feature tables"
  $featureSql = Get-Content -Raw -LiteralPath "deploy/doris/official/04_feature_tables.sql"
  Invoke-DorisSql -Sql $featureSql | Out-Null
  $technicalTemplate = Get-Content -Raw -LiteralPath "deploy/doris/official/05_technical_features_by_market.sql"
  foreach ($marketCode in @(0, 1, 103)) {
    foreach ($bucketId in 0..($TechnicalBucketCount - 1)) {
      Write-Host "Building technical features for mktcode=$marketCode bucket=$bucketId/$TechnicalBucketCount"
      $technicalSql = $technicalTemplate.Replace("__MARKET_CODE__", [string]$marketCode).Replace("__BUCKET_ID__", [string]$bucketId).Replace("__BUCKET_COUNT__", [string]$TechnicalBucketCount)
      Invoke-DorisSql -Sql $technicalSql | Out-Null
    }
  }
  $rollupSql = Get-Content -Raw -LiteralPath "deploy/doris/official/06_partitioned_rollup_serving.sql"
  Invoke-DorisSql -Sql $rollupSql | Out-Null
}

Write-Step "Validating official feature table row counts"
$featureRows = @{}
$featureRows["hsj_stock_hq_basic_prefix"] = Assert-RowCount -Table "hsj_stock_hq_basic_prefix" -Expected 13650347
$featureRows["hsj_stock_hq_ext_prefix"] = Assert-RowCount -Table "hsj_stock_hq_ext_prefix" -Expected 13650347
$featureRows["hsj_stock_hq_basic_technical"] = Assert-RowCount -Table "hsj_stock_hq_basic_technical" -Expected 13650347
$featureRows["hsj_stock_hq_basic_rollup"] = Assert-RowCount -Table "hsj_stock_hq_basic_rollup" -Expected 13650347

Write-Step "Collecting official SQL evidence"
$queryCases = @(
  [pscustomobject]@{
    name = "simple_close_price_filter"
    sql = "SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (base.closePx / 10000.0) > 10 AND base.bizdate = DATE '2026-04-14'"
  },
  [pscustomobject]@{
    name = "rank_volume_top10"
    sql = "SELECT * FROM (SELECT base.mktcode, base.tgtcode, base.bizdate, code.name, ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY base.volume DESC, base.tgtcode ASC) AS rank_no FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.bizdate = DATE '2026-04-14') AS ranked WHERE rank_no <= 10"
  },
  [pscustomobject]@{
    name = "technical_long_window_feature_filter"
    sql = "SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_hq_basic_technical AS tech ON tech.mktcode = base.mktcode AND tech.tgtcode = base.tgtcode AND tech.bizdate = base.bizdate LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.bizdate = DATE '2026-04-14' AND tech.ma250 > 0 AND tech.volume_avg_60 > 0"
  },
  [pscustomobject]@{
    name = "ext_main_net_inflow_filter"
    sql = "SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_hq_ext AS ext ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.bizdate = DATE '2026-04-14' AND ext.ZJLXMainNetTur > 0"
  },
  [pscustomobject]@{
    name = "baseline_window_volume_sum_20"
    sql = "SELECT w.mktcode, w.tgtcode, w.bizdate FROM (SELECT base.mktcode, base.tgtcode, base.bizdate, SUM(base.volume) OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS volume_sum_20 FROM newzl.hsj_stock_hq_basic AS base) AS w WHERE w.bizdate = DATE '2026-04-14' AND w.volume_sum_20 > 10000000"
  },
  [pscustomobject]@{
    name = "prefix_optimized_volume_sum_20"
    sql = "SELECT p.mktcode, p.tgtcode, p.bizdate FROM newzl.hsj_stock_hq_basic_rollup AS p WHERE p.bizdate = DATE '2026-04-14' AND p.volume_sum_20 > 10000000"
  }
)

$queryEvidence = @()
foreach ($case in $queryCases) {
  $queryEvidence += Measure-OfficialQuery -Name $case.name -Sql $case.sql
}

Write-Step "Writing official Doris evidence report"
Write-EvidenceReport -Loads $loadResults -Rows $rows -FeatureRows $featureRows -BasicDateRange $basicRange -ExtDateRange $extRange -Queries $queryEvidence

Write-Step "Done"
Write-Host "Evidence report: $EvidenceOutput"
