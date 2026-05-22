$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli scale-benchmark `
  --data-dir data/generated/scale `
  --output reports/prefix_sum_scale_benchmark.md `
  --stocks 300 `
  --days 260 `
  --window 120 `
  --iterations 5 `
  --seed 2026
