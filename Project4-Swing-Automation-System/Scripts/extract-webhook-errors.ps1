$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/..\.." | Out-Null
python tools/extract_errors.py Project4-Swing-Automation-System/test-results/webhook-logs.json