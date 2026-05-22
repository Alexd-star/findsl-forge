$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"

if (-not $env:DORIS_HOST) {
  throw "Set DORIS_HOST before collecting Doris evidence."
}

$port = if ($env:DORIS_PORT) { $env:DORIS_PORT } else { "9030" }
$user = if ($env:DORIS_USER) { $env:DORIS_USER } else { "root" }
$database = if ($env:DORIS_DATABASE) { $env:DORIS_DATABASE } else { "findsl_demo" }
$client = if ($env:DORIS_CLIENT) { $env:DORIS_CLIENT } else { "mysql" }
$iterations = if ($env:DORIS_EVIDENCE_ITERATIONS) { $env:DORIS_EVIDENCE_ITERATIONS } else { "3" }
$output = if ($env:DORIS_EVIDENCE_OUTPUT) { $env:DORIS_EVIDENCE_OUTPUT } else { "reports/doris_cluster_evidence.md" }
$password = if ($env:DORIS_PASSWORD) { $env:DORIS_PASSWORD } else { "" }
$passwordMode = if ($env:DORIS_PASSWORD_MODE) { $env:DORIS_PASSWORD_MODE } else { "none" }
$dsl = if ($env:DORIS_EVIDENCE_DSL) { $env:DORIS_EVIDENCE_DSL } else { "" }
$minSpeedup = if ($env:DORIS_EVIDENCE_MIN_SPEEDUP) { $env:DORIS_EVIDENCE_MIN_SPEEDUP } else { "10.0" }

if ($password -and $passwordMode -eq "none") {
  throw "DORIS_PASSWORD is set but DORIS_PASSWORD_MODE is none. Use inline in a private shell or prompt interactively."
}

$arguments = @(
  "-m", "findsl.cli", "collect-doris-evidence",
  "--host", $env:DORIS_HOST,
  "--port", $port,
  "--user", $user,
  "--password-mode", $passwordMode,
  "--database", $database,
  "--client", $client,
  "--iterations", $iterations,
  "--min-speedup", $minSpeedup,
  "--output", $output
)

if ($password) {
  $arguments += @("--password", $password)
}

if ($dsl) {
  $arguments += @("--dsl", $dsl)
}

& python @arguments
