param(
  [string]$ComposeFile = "deploy/doris/docker-compose.quickstart.yaml",
  [string]$FeContainer = "findsl-doris-fe-1",
  [string]$BeContainer = "findsl-doris-be-1",
  [string]$FeVolume = "findsl_doris_fe_meta",
  [string]$BeVolume = "findsl_doris_be_storage"
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

function Assert-Container([string]$Name) {
  $id = (& docker inspect --format "{{.Id}}" $Name 2>$null).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $id) { throw "Container not found: $Name" }
}

function Volume-FileCount([string]$Volume) {
  $value = & docker run --rm --entrypoint /bin/bash -v "${Volume}:/target" apache/doris:be-4.1.0 -lc "find /target -type f | wc -l"
  if ($LASTEXITCODE -ne 0) { throw "Cannot inspect volume $Volume" }
  return [int]$value.Trim()
}

Assert-Container $FeContainer
Assert-Container $BeContainer
docker volume create $FeVolume | Out-Null
docker volume create $BeVolume | Out-Null
if ((Volume-FileCount $FeVolume) -gt 0 -or (Volume-FileCount $BeVolume) -gt 0) {
  throw "Target named volumes are not empty; refusing to overwrite them."
}

$copied = $false
$snapshotTag = "findsl-doris-volume-migration-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$feSnapshot = "${snapshotTag}-fe"
$beSnapshot = "${snapshotTag}-be"
try {
  docker stop $BeContainer $FeContainer | Out-Null
  docker commit $FeContainer $feSnapshot | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "FE snapshot creation failed" }
  docker commit $BeContainer $beSnapshot | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "BE snapshot creation failed" }
  docker run --rm --entrypoint /bin/bash -v "${FeVolume}:/target" $feSnapshot -lc "cp -a /opt/apache-doris/fe/doris-meta/. /target/"
  if ($LASTEXITCODE -ne 0) { throw "FE metadata copy failed" }
  docker run --rm --entrypoint /bin/bash -v "${BeVolume}:/target" $beSnapshot -lc "cp -a /opt/apache-doris/be/storage/. /target/"
  if ($LASTEXITCODE -ne 0) { throw "BE storage copy failed" }
  $feFiles = Volume-FileCount $FeVolume
  $beFiles = Volume-FileCount $BeVolume
  if ($feFiles -lt 1 -or $beFiles -lt 1) { throw "Copied volumes failed non-empty verification" }
  Write-Host "Volume copy verified: FE files=$feFiles, BE files=$beFiles" -ForegroundColor Green
  $copied = $true
} finally {
  docker image rm $feSnapshot $beSnapshot 2>$null | Out-Null
  if (-not $copied) {
    docker start $FeContainer $BeContainer | Out-Null
  }
}

docker compose -f $ComposeFile down
if ($LASTEXITCODE -ne 0) { throw "Cannot replace old quickstart containers" }
docker compose -f $ComposeFile up -d
if ($LASTEXITCODE -ne 0) { throw "Cannot start persistent quickstart containers" }
powershell -ExecutionPolicy Bypass -File .\scripts\doris_quickstart.ps1 -Action Health -ComposeFile $ComposeFile
Write-Host "Doris persistent-volume migration: PASS" -ForegroundColor Green
