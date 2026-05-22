$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli official-suite `
  --positive-input data/samples/official_positive_cases.jsonl `
  --negative-input data/samples/official_negative_cases.jsonl `
  --data-dir data/samples `
  --output reports/official_suite_report.md
