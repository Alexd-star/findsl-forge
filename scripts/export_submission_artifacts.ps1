param(
  [string]$ArtifactsDir = "submission_artifacts",
  [string]$ReportsDir = "reports"
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$reportFiles = @(
  "submission_readiness.md",
  "doris_cluster_evidence.md",
  "doris_cluster_evidence.json",
  "official_suite_report.md",
  "official_doris_evidence.md",
  "official_doris_evidence.json",
  "official_slot_coverage.md",
  "official_slot_coverage.json",
  "official_compiler_funnel.md",
  "official_compiler_funnel.json",
  "official_correctness_benchmark.md",
  "official_correctness_benchmark.json",
  "official_compile_latency.md",
  "official_compile_latency.json",
  "official_long_horizon_matrix.md",
  "official_long_horizon_matrix.json",
  "official_full_performance_matrix.md",
  "official_full_performance_matrix.json",
  "official_capability_matrix.md",
  "official_capability_matrix.json",
  "blind_extension_evidence.md",
  "blind_extension_evidence.json",
  "hero_query.md",
  "hero_query.json",
  "official_doris_watermark.md",
  "official_doris_watermark.json",
  "adjustment_policy_doris.md",
  "adjustment_policy_doris.json",
  "performance_evidence_registry.md",
  "performance_evidence_registry.json",
  "current_official_gap_taxonomy.md",
  "current_official_gap_taxonomy.json",
  "current_external_data_inventory.md",
  "current_external_data_inventory.json",
  "current_scope_data_gap_audit.md",
  "current_scope_data_gap_audit.json",
  "p0p1_date_scope_delta_doris.md",
  "p0p1_date_scope_delta_doris.json",
  "phase42_long_horizon_doris.md",
  "phase42_long_horizon_doris.json",
  "external_catalog_doris_load.json",
  "phase48_scope_semantic_policy_funnel.md",
  "phase48_scope_semantic_policy_funnel.json",
  "phase48_scope_semantic_policy_delta_doris_audit.md",
  "phase48_scope_semantic_policy_delta_doris_audit.json",
  "phase48_scope_semantic_policy_doris.md",
  "phase48_scope_semantic_policy_doris.json",
  "phase48_true_remaining_scope_targets.json",
  "phase48_scope_semantic_policy.json",
  "phase6c_set_prefix_doris.md",
  "phase6c_set_prefix_doris.json"
)

$status = ""
try {
  $statusLines = & git status --short
  $status = ($statusLines | Where-Object {
      $_ -notmatch "submission_artifacts/evidence_manifest\.md" -and
      $_ -notmatch "submission_artifacts/evidence_snapshots" -and
      $_ -notmatch "scripts/export_submission_artifacts\.ps1"
    }) -join "`n"
} catch {
  $status = "<unknown>"
}
if (-not $status) {
  $status = "clean"
}

$snapshotDir = Join-Path $ArtifactsDir "evidence_snapshots"
$artifactsRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $ArtifactsDir))
$snapshotRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $snapshotDir))
if ([System.IO.Path]::GetDirectoryName($snapshotRoot) -ne $artifactsRoot) {
  throw "Refusing to rebuild evidence snapshots outside the artifact root: $snapshotRoot"
}
if (Test-Path -LiteralPath $snapshotRoot) {
  Remove-Item -LiteralPath $snapshotRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $snapshotDir | Out-Null

$copied = @()
foreach ($file in $reportFiles) {
  $source = Join-Path $ReportsDir $file
  $destination = Join-Path $snapshotDir $file
  if (Test-Path $source) {
    Copy-Item -Force -Path $source -Destination $destination
  }
  if (Test-Path $destination) {
    $copied += $file
  }
}
$copied = @(
  Get-ChildItem -LiteralPath $snapshotDir -File |
    Sort-Object Name |
    ForEach-Object { $_.Name }
)

$screenshotSource = Join-Path (Get-Location) "output/playwright"
$screenshotDestination = Join-Path $ArtifactsDir "product_screenshots"
if (Test-Path -LiteralPath $screenshotDestination) {
  Remove-Item -LiteralPath $screenshotDestination -Recurse -Force
}
if (Test-Path -LiteralPath $screenshotSource) {
  New-Item -ItemType Directory -Force -Path $screenshotDestination | Out-Null
  Get-ChildItem -LiteralPath $screenshotSource -File -Filter *.png |
    Copy-Item -Destination $screenshotDestination -Force
}

$readinessSnapshot = Join-Path $snapshotDir "submission_readiness.md"
if (Test-Path $readinessSnapshot) {
  $readiness = Get-Content -Raw -Encoding UTF8 -Path $readinessSnapshot
  $readiness = $readiness -replace "- Git HEAD: ", "- Git HEAD at report generation: "
  [System.IO.File]::WriteAllText((Resolve-Path $readinessSnapshot), $readiness, $utf8NoBom)
}

$head = ""
try {
  $head = (& git rev-parse --short HEAD).Trim()
} catch {
  $head = "<unknown>"
}

$manifest = @()
$manifest += "# Evidence Snapshot Manifest"
$manifest += ""
$manifest += "- Generated at: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
$manifest += "- Git HEAD at export: $head"
$manifest += "- Git status when exported, excluding evidence snapshots and this export script: $status"
$manifest += "- Source reports directory: $ReportsDir"
$manifest += "- Snapshot directory: $snapshotDir"
$manifest += ""
$manifest += "## Included Files"
$manifest += ""
foreach ($file in $copied) {
  $length = (Get-Item (Join-Path $snapshotDir $file)).Length
  $manifest += ('- `{0}` ({1} bytes)' -f $file, $length)
}
if (Test-Path -LiteralPath $screenshotDestination) {
  foreach ($image in Get-ChildItem -LiteralPath $screenshotDestination -File | Sort-Object Name) {
    $manifest += ('- `product_screenshots/{0}` ({1} bytes)' -f $image.Name, $image.Length)
  }
}
$manifest += ""
$manifest += "## Excluded By Design"
$manifest += ""
$manifest += '- `data/generated/`: large reproducible scale CSV files, regenerated by `scripts/prepare_doris_scale_evidence.ps1`.'
$manifest += "- Docker volumes and Doris runtime data: environment state, not source-controlled evidence."
$manifest += "- PPT, video, and long manuals are deferred; only reproducible product QA screenshots are included here."

$manifestPath = Join-Path $ArtifactsDir "evidence_manifest.md"
[System.IO.File]::WriteAllText(
  (Join-Path (Get-Location) $manifestPath),
  (($manifest -join "`n") + "`n"),
  $utf8NoBom
)

$metadataPath = Join-Path $ArtifactsDir "evidence_metadata.json"
$summaryPath = Join-Path $ArtifactsDir "evidence_summary.md"
Remove-Item -LiteralPath $metadataPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $summaryPath -Force -ErrorAction SilentlyContinue
$env:PYTHONPATH = "src"
& python -m findsl.cli evidence-metadata `
  --snapshots-dir $snapshotDir `
  --manifest $manifestPath `
  --output $metadataPath `
  --summary-output $summaryPath `
  --contract "configs/official/evidence_contract.json" `
  --expected-git-head $head `
  --require-contract-pass | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Evidence metadata contract failed with exit code $LASTEXITCODE"
}

Write-Host "Exported $($copied.Count) evidence files into $snapshotDir"
Write-Host "Manifest: $manifestPath"
Write-Host "Metadata: $metadataPath"
Write-Host "Summary: $summaryPath"
