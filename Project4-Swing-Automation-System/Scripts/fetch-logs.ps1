param(
  [string]$FunctionName = "swing-webhook-trading",
  [int]$Days = 1,
  [string]$OutPath = "Project4-Swing-Automation-System/test-results/webhook-logs.json"
)
$ErrorActionPreference = 'Stop'
# Ensure working directory at repo root
Set-Location "$PSScriptRoot/..\.." | Out-Null
$null = New-Item -ItemType Directory -Force "Project4-Swing-Automation-System/test-results" | Out-Null
$since = (Get-Date).AddDays(-$Days)
$start = [int64]([DateTimeOffset]$since).ToUnixTimeMilliseconds()
aws logs filter-log-events --log-group-name "/aws/lambda/$FunctionName" --start-time $start --limit 500 --no-cli-pager --output json | Out-File -Encoding utf8 $OutPath
Write-Host "Saved logs to $OutPath"