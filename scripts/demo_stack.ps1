param(
    [ValidateSet("Start", "Stop", "Status")]
    [string]$Action = "Start",
    [switch]$SkipDoris,
    [switch]$SkipSampleLoad,
    [string]$ProxyUrl = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DorisCompose = Join-Path $RepoRoot "deploy\doris\docker-compose.quickstart.yaml"
$DemoCompose = Join-Path $RepoRoot "deploy\demo\compose.yaml"

if (-not $ProxyUrl) {
    $ProxyUrl = $env:HTTPS_PROXY
}
if ($ProxyUrl) {
    $dockerProxy = $ProxyUrl.Replace("127.0.0.1", "host.docker.internal").Replace("localhost", "host.docker.internal")
    $env:FINDSL_DOCKER_HTTP_PROXY = $dockerProxy
    $env:FINDSL_DOCKER_HTTPS_PROXY = $dockerProxy
    $env:FINDSL_DOCKER_NO_PROXY = "127.0.0.1,localhost,host.docker.internal,172.20.80.0/24"
}

function Invoke-Compose([string]$File, [string[]]$Arguments) {
    & docker compose -f $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed for $File"
    }
}

function Wait-Doris {
    $mysql = (Get-Command mysql.exe -ErrorAction Stop).Source
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        & $mysql --batch --skip-column-names --host 127.0.0.1 --port 9030 --user root --execute "SHOW BACKENDS" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $mysql
        }
        Start-Sleep -Seconds 3
    }
    throw "Apache Doris did not become ready within 180 seconds"
}

function Load-Sample([string]$Mysql) {
    $sqlFiles = @(
        "deploy\doris\01_schema.sql",
        "deploy\doris\02_sample_data.sql",
        "deploy\doris\03_build_prefix_tables.sql",
        "deploy\doris\04_smoke_queries.sql"
    )
    foreach ($relative in $sqlFiles) {
        $path = Join-Path $RepoRoot $relative
        Get-Content -LiteralPath $path -Raw -Encoding UTF8 |
            & $Mysql --default-character-set=utf8mb4 --host 127.0.0.1 --port 9030 --user root
        if ($LASTEXITCODE -ne 0) {
            throw "Doris sample initialization failed: $relative"
        }
    }
}

function Wait-Demo {
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 3
            if ($health.ok) {
                return
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Invoke-Compose $DemoCompose @("logs", "--tail", "100")
    throw "FinDSL demo did not become healthy within 20 seconds"
}

if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required and docker.exe is not available"
}

switch ($Action) {
    "Start" {
        if (-not $SkipDoris) {
            Invoke-Compose $DorisCompose @("up", "-d")
            $mysql = Wait-Doris
            if (-not $SkipSampleLoad) {
                Load-Sample $mysql
            }
        }
        Invoke-Compose $DemoCompose @("up", "-d", "--build")
        Wait-Demo
        Write-Host "FinDSL Forge is ready: http://127.0.0.1:8765"
    }
    "Stop" {
        Invoke-Compose $DemoCompose @("down")
        if (-not $SkipDoris) {
            Invoke-Compose $DorisCompose @("down")
        }
        Write-Host "FinDSL Forge services stopped; Doris volumes were preserved"
    }
    "Status" {
        Invoke-Compose $DemoCompose @("ps")
        if (-not $SkipDoris) {
            Invoke-Compose $DorisCompose @("ps")
        }
    }
}
