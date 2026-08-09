param(
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 8766,
  [switch]$EnableExecute
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $RepoRoot "deploy/api/service.env"
if (-not (Test-Path -LiteralPath $EnvPath)) {
  $secretBytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
  $apiKey = [Convert]::ToHexString($secretBytes).ToLowerInvariant()
  $executeValue = if ($EnableExecute) { "true" } else { "false" }
  @(
    "FINDSL_ENV=production"
    "FINDSL_API_KEY=$apiKey"
    "FINDSL_MAX_CONCURRENCY=8"
    "FINDSL_QUEUE_TIMEOUT_SECONDS=1"
    "FINDSL_REQUESTS_PER_MINUTE=120"
    "FINDSL_AUDIT_LOG=$RepoRoot/output/logs/api-audit.jsonl"
    "FINDSL_ENABLE_EXECUTE=$executeValue"
    "FINDSL_DORIS_HOST=127.0.0.1"
    "FINDSL_DORIS_PORT=9030"
    "FINDSL_DORIS_USER=findsl_readonly"
    "FINDSL_DORIS_PASSWORD="
    "FINDSL_DORIS_DATABASE=newzl"
    "FINDSL_DORIS_TIMEOUT_SECONDS=10"
  ) | Set-Content -LiteralPath $EnvPath -Encoding UTF8
  Write-Host "Generated API credential in $EnvPath"
}

$envValues = Get-Content -LiteralPath $EnvPath -Encoding UTF8
foreach ($line in $envValues) {
  if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
  $name, $value = $line.Split("=", 2)
  [Environment]::SetEnvironmentVariable($name, $value, "Process")
}

python -m findsl.cli serve-api --host $HostAddress --port $Port
