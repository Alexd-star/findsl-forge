$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli serve-demo `
  --host 127.0.0.1 `
  --port 8765 `
  --data-dir data/samples `
  --input data/samples/queries.jsonl
