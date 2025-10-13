param(
  [string]$Region = "us-east-1",
  [string]$DashboardName = "swing-ops-dashboard"
)
$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/..\.." | Out-Null
$file = Resolve-Path "Project4-Swing-Automation-System/deployment/cloudwatch-dashboard.json"
aws cloudwatch put-dashboard --region $Region --dashboard-name $DashboardName --dashboard-body ("file://" + $file)
if ($LASTEXITCODE -ne 0) { throw "put-dashboard failed ($LASTEXITCODE)" }
Write-Host "Deployed CloudWatch Dashboard: $DashboardName"