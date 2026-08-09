param(
  [ValidateSet("Start", "Health", "Status", "Rebuild", "Stop")]
  [string]$Action = "Start",
  [string]$ComposeFile = "deploy/doris/docker-compose.quickstart.yaml",
  [string]$DorisHost = "127.0.0.1",
  [int]$QueryPort = 9030,
  [string]$User = "root",
  [string]$Password = "",
  [string]$MySql = "mysql",
  [int]$TimeoutSeconds = 480
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:NO_PROXY = "127.0.0.1,localhost,172.20.80.0/24"
$env:no_proxy = $env:NO_PROXY

function Assert-Tool([string]$Name) {
  $tool = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $tool) { throw "Required tool is not available: $Name" }
  return $tool.Source
}

function Invoke-DorisSql([string]$Sql) {
  $args = @("-h", $DorisHost, "-P", [string]$QueryPort, "-u", $User,
    "--connect-timeout", "10", "--batch", "--raw", "--skip-column-names",
    "--default-character-set=utf8mb4")
  if ($Password) { $args += "-p$Password" }
  $args += @("-e", $Sql)
  $output = & $MySql @args 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Doris SQL health check failed: $output" }
  return ($output | Out-String).Trim()
}

function Wait-Doris {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $last = ""
  while ((Get-Date) -lt $deadline) {
    try {
      $fe = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "http://127.0.0.1:8030/api/bootstrap"
      $be = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "http://127.0.0.1:8040/api/health"
      $backends = Invoke-DorisSql "SHOW BACKENDS;"
      if ($fe.StatusCode -eq 200 -and $be.StatusCode -eq 200 -and $backends -match "\btrue\b") {
        Write-Host "Doris health: PASS (FE HTTP, BE HTTP, query port and alive backend)" -ForegroundColor Green
        return
      }
      $last = $backends
    } catch {
      $last = $_.Exception.Message
    }
    Start-Sleep -Seconds 5
  }
  throw "Doris did not become healthy before timeout. Last status: $last"
}

Assert-Tool "docker" | Out-Null
if ($Action -in @("Start", "Health", "Rebuild")) { Assert-Tool $MySql | Out-Null }

switch ($Action) {
  "Start" {
    docker compose -f $ComposeFile up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose start failed" }
    Wait-Doris
  }
  "Health" { Wait-Doris }
  "Status" { docker compose -f $ComposeFile ps }
  "Rebuild" {
    docker compose -f $ComposeFile up -d --force-recreate
    if ($LASTEXITCODE -ne 0) { throw "docker compose rebuild failed" }
    Wait-Doris
  }
  "Stop" {
    docker compose -f $ComposeFile stop
    if ($LASTEXITCODE -ne 0) { throw "docker compose stop failed" }
    Write-Host "Doris containers stopped; named volumes were preserved."
  }
}
