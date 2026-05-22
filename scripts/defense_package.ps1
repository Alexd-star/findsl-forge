$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli defense-package `
  --output reports/defense_package.md `
  --data-dir data/samples `
  --input data/samples/queries.jsonl `
  --positive-input data/samples/official_positive_cases.jsonl `
  --negative-input data/samples/official_negative_cases.jsonl `
  --repo-root .
