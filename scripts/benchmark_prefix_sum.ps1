$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
$dsl = 'filter(SUM(indicator("volume"), 3) > 300)'
python -m findsl.cli benchmark-prefix-sum $dsl --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.md
