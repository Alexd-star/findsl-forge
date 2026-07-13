param(
  [string]$Catalog = "data/external_catalog/catalog.sqlite3",
  [string]$DataDir = "data/external_catalog/doris",
  [string]$DorisHost = "127.0.0.1",
  [int]$QueryPort = 9030,
  [string]$StreamLoadHost = "127.0.0.1",
  [int]$StreamLoadPort = 8040,
  [string]$User = "root",
  [string]$Password = "",
  [string]$Client = "mysql",
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"

function Invoke-DorisSql {
  param([string]$Sql)
  $args = @("-h", $DorisHost, "-P", [string]$QueryPort, "-u", $User,
    "--connect-timeout", "10", "--batch", "--raw", "--default-character-set=utf8mb4")
  if ($Password) { $args += "-p$Password" }
  $args += @("-e", $Sql)
  $output = & $Client @args 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Doris SQL failed: $Sql`n$output" }
  return ($output | Out-String).Trim()
}

function Invoke-ExternalStreamLoad {
  param([string]$Table, [string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { throw "CSV not found: $Path" }
  $label = "findsl_external_${Table}_$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmssfff'))"
  $url = "http://${StreamLoadHost}:${StreamLoadPort}/api/findsl_ext/${Table}/_stream_load"
  $response = & curl.exe --fail-with-body --show-error --silent --location-trusted `
    -u "${User}:${Password}" -T (Resolve-Path -LiteralPath $Path).Path `
    -H "Expect: 100-continue" -H "label: $label" -H "format: csv" `
    -H "column_separator:," -H "skip_lines:1" -H "strict_mode:true" `
    -H "max_filter_ratio:0" -H "timeout:600" $url
  if ($LASTEXITCODE -ne 0) { throw "Stream Load failed for ${Table}: $response" }
  $payload = $response | ConvertFrom-Json
  if ($payload.Status -notin @("Success", "Publish Timeout")) {
    throw "Stream Load failed for ${Table}: $($payload.Status) $($payload.Message)"
  }
  if ([int64]$payload.NumberFilteredRows -ne 0) {
    throw "Stream Load filtered rows for ${Table}: $($payload.NumberFilteredRows)"
  }
  return $payload
}

& $Python -c "import findsl" *> $null
if ($LASTEXITCODE -ne 0) { throw "Project Python environment is unavailable" }

& $Python -c "from pathlib import Path; from findsl.official.external import ExternalCatalog; ExternalCatalog(Path(r'$Catalog')).export_doris(Path(r'$DataDir'))"
if ($LASTEXITCODE -ne 0) { throw "External catalog CSV export failed" }

Invoke-DorisSql -Sql (Get-Content deploy/doris/official/06_external_catalog.sql -Raw) | Out-Null
$manifest = Get-Content (Join-Path $DataDir "manifest.json") -Raw | ConvertFrom-Json
$results = [ordered]@{}
foreach ($table in @("scope_membership", "industry_membership", "instrument_rule")) {
  Invoke-DorisSql -Sql "TRUNCATE TABLE findsl_ext.${table};" | Out-Null
  $load = Invoke-ExternalStreamLoad -Table $table -Path (Join-Path $DataDir "${table}.csv")
  $actualText = Invoke-DorisSql -Sql "SELECT COUNT(*) AS row_count FROM findsl_ext.${table};"
  $actual = [int64](($actualText -split "\r?\n")[-1])
  $expected = [int64]$manifest.exports.$table.rows
  if ($actual -ne $expected) { throw "Row count mismatch for ${table}: expected $expected, got $actual" }
  $results[$table] = [ordered]@{
    expected_rows = $expected
    actual_rows = $actual
    stream_load_status = $load.Status
    filtered_rows = [int64]$load.NumberFilteredRows
  }
}

$evidence = [ordered]@{
  schema_version = 1
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  catalog = (Resolve-Path -LiteralPath $Catalog).Path
  doris = "${DorisHost}:${QueryPort}"
  status = "PASS"
  tables = $results
}
$evidence | ConvertTo-Json -Depth 8 | Set-Content reports/external_catalog_doris_load.json -Encoding utf8
$evidence | ConvertTo-Json -Depth 8
