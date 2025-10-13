param(
  [string]$Region = "us-east-1"
)
$ErrorActionPreference = 'Stop'
$body = Get-Content (Join-Path (Split-Path $PSScriptRoot -Parent) 'deployment' 'cloudwatch-dashboard.json') -Raw
aws cloudwatch put-dashboard --dashboard-name tradeauto-ops-dashboard --dashboard-body file://(Join-Path (Split-Path $PSScriptRoot -Parent) 'deployment' 'cloudwatch-dashboard.json') --region $Region
Write-Host "Deployed dashboard tradeauto-ops-dashboard"
