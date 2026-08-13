param(
  [string]$TeamName = "FinDSLForge",
  [string]$OutputRoot = "final_submission"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$env:PYTHONPATH = "src"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$head = (& git rev-parse HEAD).Trim()
$dirty = (& git status --short --untracked-files=no) -join "`n"
if ($dirty) {
  throw "Commit tracked changes before packaging:`n$dirty"
}

$requiredEvidence = @(
  "final_submission_metadata.json",
  "final_submission_summary.md",
  "final_quality_gates.json",
  "final_quality_gates.md",
  "official_doris_watermark.json",
  "official_doris_watermark.md",
  "official_correctness_benchmark.json",
  "official_correctness_benchmark.md",
  "official_full_performance_matrix.json",
  "official_full_performance_matrix.md",
  "official_long_horizon_matrix.json",
  "official_long_horizon_matrix.md",
  "official_compile_latency.json",
  "official_compile_latency.md",
  "official_capability_matrix.json",
  "official_capability_matrix.md",
  "blind_extension_evidence.json",
  "blind_extension_evidence.md",
  "hero_query.json",
  "hero_query.md",
  "group_entity_doris.json",
  "group_entity_doris.md",
  "official_suite_report.md"
)
foreach ($file in $requiredEvidence) {
  if (-not (Test-Path -LiteralPath (Join-Path "reports" $file) -PathType Leaf)) {
    throw "Required final evidence is missing: reports/$file"
  }
}
$metadata = Get-Content -LiteralPath reports/final_submission_metadata.json -Raw -Encoding UTF8 | ConvertFrom-Json
if ($metadata.git_head -ne $head -or -not $metadata.all_gates_passed) {
  throw "Final metadata is not bound to current HEAD or its gates did not pass."
}

$outputFull = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
$repoFull = [System.IO.Path]::GetFullPath($repoRoot)
if (-not $outputFull.StartsWith($repoFull, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "OutputRoot must stay inside the repository."
}
if (Test-Path -LiteralPath $outputFull) {
  Remove-Item -LiteralPath $outputFull -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outputFull | Out-Null

$packageName = "揭榜挂帅-19-$TeamName"
$packageRoot = Join-Path $outputFull $packageName
$sourceRoot = Join-Path $packageRoot "01_可运行项目\FinDSL-Forge"
$evidenceRoot = Join-Path $packageRoot "02_测试与证据"
$notesRoot = Join-Path $packageRoot "03_提交说明"
New-Item -ItemType Directory -Force -Path $sourceRoot, $evidenceRoot, $notesRoot | Out-Null

$sourceArchive = Join-Path $outputFull "source-$head.zip"
& git archive --format=zip --output=$sourceArchive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Expand-Archive -LiteralPath $sourceArchive -DestinationPath $sourceRoot -Force
Remove-Item -LiteralPath $sourceArchive -Force

foreach ($relative in @("docs", "submission_artifacts", "PROJECT_INDEX.md", "CHANGELOG.md")) {
  $target = Join-Path $sourceRoot $relative
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path (Join-Path $sourceRoot "docs") | Out-Null
Copy-Item -LiteralPath docs/架构设计.md -Destination (Join-Path $sourceRoot "docs\架构设计.md")
Copy-Item -LiteralPath docs/运行测试与Doris.md -Destination (Join-Path $sourceRoot "docs\运行测试与Doris.md")

foreach ($file in $requiredEvidence) {
  Copy-Item -LiteralPath (Join-Path "reports" $file) -Destination (Join-Path $evidenceRoot $file)
}
if (-not (Test-Path -LiteralPath output/playwright/delivery-evidence-desktop.png)) {
  throw "Final product screenshots are missing; run the Playwright capture before packaging."
}
New-Item -ItemType Directory -Force -Path (Join-Path $evidenceRoot "产品截图") | Out-Null
foreach ($image in @("delivery-evidence-desktop.png", "hero-route-desktop.png", "hero-route-mobile.png")) {
  Copy-Item -LiteralPath (Join-Path "output/playwright" $image) -Destination (Join-Path $evidenceRoot "产品截图\$image")
}

[System.IO.File]::WriteAllText((Join-Path $packageRoot "readme.txt"), @"
FinDSL Forge 赛题19工程交付包

01_可运行项目：完整源码、配置、ANTLR4文法、Doris部署资产、测试与样例。
02_测试与证据：同一Git提交和同一Doris快照生成的正确率、性能、编译延迟、扩展性与工程门禁证据。
03_提交说明：版本身份、运行环境、文件清单和校验结果。

推荐从 03_提交说明/readme.txt 开始阅读，并按 01_可运行项目/readme.txt 完成部署。
"@, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "01_可运行项目\readme.txt"), @"
本目录包含可独立安装运行的 FinDSL Forge 工程。

入口：FinDSL-Forge/README.md
依赖：FinDSL-Forge/pyproject.toml
编译器：FinDSL-Forge/src/findsl/official/
文法：FinDSL-Forge/grammar/OfficialSlot.g4
配置：FinDSL-Forge/configs/official/
Doris部署：FinDSL-Forge/deploy/doris/
测试：FinDSL-Forge/tests/

安装后执行 python -m pytest -q，可复现源码质量门禁；Doris完整流程见 docs/运行测试与Doris.md。
"@, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $evidenceRoot "readme.txt"), @"
本目录保存最终评分证据。所有JSON为机器可读原始结果，Markdown为对应的人读摘要。

首先阅读 final_submission_summary.md；final_submission_metadata.json 记录全部门禁、Git HEAD、数据快照和证据文件SHA-256。正确率采用独立Reference SQL完整结果集对拍，性能采用真实Apache Doris重复执行与P95统计。
"@, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $notesRoot "readme.txt"), @"
发布版本：见 RELEASE_COMMIT.txt
文件完整性：见 FILE_MANIFEST.sha256
自动校验：见 PACKAGE_VERIFICATION.md 和 PACKAGE_VERIFICATION.json

快速运行：
1. 进入 01_可运行项目/FinDSL-Forge。
2. 使用 Python 3.11 执行 python -m pip install -e ".[dev]"。
3. 执行 python -m pytest -q。
4. 执行 pwsh -File .\scripts\demo_stack.ps1 启动 Doris 与演示服务。
5. 浏览器访问 http://127.0.0.1:8765。
"@, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $notesRoot "RELEASE_COMMIT.txt"), "$head`n", $utf8NoBom)

python scripts/verify_submission_package.py `
  --package-dir $packageRoot `
  --json-output (Join-Path $notesRoot "PACKAGE_VERIFICATION.json") `
  --report-output (Join-Path $notesRoot "PACKAGE_VERIFICATION.md")
if ($LASTEXITCODE -ne 0) { throw "Pre-archive package verification failed" }

$manifestPath = Join-Path $notesRoot "FILE_MANIFEST.sha256"
$manifestLines = Get-ChildItem -LiteralPath $packageRoot -Recurse -File |
  Where-Object { $_.FullName -ne $manifestPath } |
  Sort-Object FullName |
  ForEach-Object {
    $relative = [System.IO.Path]::GetRelativePath($packageRoot, $_.FullName).Replace("\", "/")
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
  }
[System.IO.File]::WriteAllText($manifestPath, (($manifestLines -join "`n") + "`n"), $utf8NoBom)

$zipPath = Join-Path $outputFull "$packageName.zip"
Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
python scripts/verify_submission_package.py --package-dir $packageRoot --zip $zipPath
if ($LASTEXITCODE -ne 0) { throw "Final ZIP verification failed" }

Write-Host "Submission directory: $packageRoot" -ForegroundColor Green
Write-Host "Submission ZIP: $zipPath" -ForegroundColor Green
Write-Host "ZIP SHA-256: $((Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant())" -ForegroundColor Green
