$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python -m findsl.cli readiness-report `
  --output reports/submission_readiness.md `
  --reports-dir reports `
  --input data/samples/queries.jsonl `
  --data-dir data/samples `
  --benchmark-iterations 20
