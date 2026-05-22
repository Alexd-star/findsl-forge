$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli emit-doris-assets --data-dir data/samples --output-dir deploy/doris --database findsl_demo --buckets 8 --replication-num 1
