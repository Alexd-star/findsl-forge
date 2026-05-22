$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli evaluate --input data/samples/queries.jsonl --output reports/evaluation_report.md
