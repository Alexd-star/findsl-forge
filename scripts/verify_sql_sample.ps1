$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
$dsl = 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))'
python -m findsl.cli verify-sql $dsl --data-dir data/samples --json
