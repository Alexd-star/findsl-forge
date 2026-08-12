param(
  [string]$Data = "data/external_catalog/index_quote.csv",
  [string]$DorisHost = "127.0.0.1",
  [int]$QueryPort = 9030,
  [string]$StreamLoadHost = "127.0.0.1",
  [int]$StreamLoadPort = 8040,
  [string]$User = "root",
  [string]$Password = "",
  [string]$Client = "mysql",
  [string]$LoadLabelRunId = "v1"
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

function Invoke-DorisSql([string]$Sql) {
  $args = @("-h", $DorisHost, "-P", [string]$QueryPort, "-u", $User,
    "--batch", "--raw", "--default-character-set=utf8mb4")
  if ($Password) { $args += "-p$Password" }
  $args += @("-e", $Sql)
  $output = & $Client @args 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Doris SQL failed: $Sql`n$output" }
  return ($output | Out-String).Trim()
}

if (-not (Test-Path -LiteralPath $Data)) { throw "Index quote CSV not found: $Data" }
Invoke-DorisSql (Get-Content deploy/doris/official/06_external_catalog.sql -Raw) | Out-Null
$env:NO_PROXY = "127.0.0.1,localhost,172.20.80.0/24"
$env:no_proxy = $env:NO_PROXY
$expected = (Import-Csv -LiteralPath $Data).Count
$actualText = Invoke-DorisSql "SELECT COUNT(*) FROM findsl_ext.index_quote;"
$actual = [int64](($actualText -split "\r?\n")[-1])
$fileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Data).Hash.ToLowerInvariant().Substring(0, 16)
$label = "findsl_index_quote_${fileHash}_${LoadLabelRunId}"
$load = [pscustomobject]@{ Status = "AlreadyLoaded"; NumberFilteredRows = 0 }
if ($actual -ne $expected) {
Invoke-DorisSql "TRUNCATE TABLE findsl_ext.index_quote;" | Out-Null
$url = "http://${StreamLoadHost}:${StreamLoadPort}/api/findsl_ext/index_quote/_stream_load"
$response = & curl.exe --fail-with-body --show-error --silent --location-trusted `
  -u "${User}:${Password}" -T (Resolve-Path -LiteralPath $Data).Path `
  -H "Expect: 100-continue" -H "label: $label" -H "format: csv" `
  -H "column_separator:," -H "skip_lines:1" -H "strict_mode:true" `
  -H "max_filter_ratio:0" -H "timeout:600" $url
if ($LASTEXITCODE -ne 0) { throw "Index quote Stream Load failed: $response" }
$load = $response | ConvertFrom-Json
if ($load.Status -notin @("Success", "Publish Timeout") -or [int64]$load.NumberFilteredRows -ne 0) {
  throw "Index quote Stream Load rejected data: $response"
}
$actualText = Invoke-DorisSql "SELECT COUNT(*) FROM findsl_ext.index_quote;"
$actual = [int64](($actualText -split "\r?\n")[-1])
}
if ($actual -ne $expected) { throw "Index quote row mismatch: $expected/$actual" }
Invoke-DorisSql "TRUNCATE TABLE findsl_ext.index_quote_security_shape;" | Out-Null
Invoke-DorisSql @"
INSERT INTO findsl_ext.index_quote_security_shape
SELECT 0,index_code,bizdate,snapshot_id,open,high,low,close,volume,pct_change
FROM findsl_ext.index_quote;
"@ | Out-Null
$shapeText = Invoke-DorisSql "SELECT COUNT(*) FROM findsl_ext.index_quote_security_shape;"
$shapeRows = [int64](($shapeText -split "\r?\n")[-1])
if ($shapeRows -ne $expected) { throw "Index quote shape row mismatch: $expected/$shapeRows" }
$evidence = [ordered]@{
  schema_version = 1
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  git_head = (& git rev-parse HEAD).Trim()
  status = "PASS"
  expected_rows = $expected
  actual_rows = $actual
  shape_rows = $shapeRows
  filtered_rows = [int64]$load.NumberFilteredRows
}
$evidence | ConvertTo-Json -Depth 6 | Set-Content reports/index_quote_doris_load.json -Encoding utf8
$evidence | ConvertTo-Json -Depth 6
