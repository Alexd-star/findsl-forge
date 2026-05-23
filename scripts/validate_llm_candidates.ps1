$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "src"
python -m findsl.cli validate-llm-candidates `
  --response-file data/samples/llm_candidate_response.json `
  --text "近3日成交量累计大于300" `
  --data-dir data/samples `
  --json
