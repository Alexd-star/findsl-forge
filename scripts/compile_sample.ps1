$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
$dsl = 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))'
python -m findsl.cli compile $dsl --json
