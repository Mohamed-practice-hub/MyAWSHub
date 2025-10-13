param(
  [string]$Region = "us-east-1",
  [string]$WebhookFunction = "swing-webhook-trading",
  [string]$PortfolioFunction = "swing-portfolio-reporter"
)
$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/..\.." | Out-Null

function New-TempZipPath($name) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  return Join-Path $env:TEMP "$name-$stamp.zip"
}

# Rebuild webhook zip to temp path
$webhookDir = "Project4-Swing-Automation-System/deployment/webhook-trading"
$webhookZipTemp = New-TempZipPath "webhook-trading"
if (Test-Path $webhookZipTemp) { Remove-Item $webhookZipTemp -Force }
if (Test-Path $webhookDir) {
  if (Test-Path $webhookZipTemp) { Remove-Item $webhookZipTemp -Force }
  if (Test-Path $webhookZipTemp) { Start-Sleep -Milliseconds 200 }
  if (Test-Path $webhookZipTemp) { throw "Cannot remove temp zip $webhookZipTemp" }
  if (Test-Path $webhookZipTemp) { Remove-Item $webhookZipTemp -Force }
  if (Test-Path $webhookZipTemp) { Start-Sleep -Milliseconds 100 }
  if (Test-Path $webhookZipTemp) { throw "Temp zip still exists" }
  if (Test-Path $webhookZipTemp) { Start-Sleep -Milliseconds 50 }
  if (Test-Path $webhookZipTemp) { throw "Temp zip cleanup failed" }
  if (Test-Path $webhookZipTemp) { Remove-Item $webhookZipTemp -Force }
  if (Test-Path $webhookZipTemp) { throw "Failed to remove temp zip path" }
  if (Test-Path $webhookZipTemp) { Start-Sleep -Milliseconds 50 }
  if (Test-Path $webhookZipTemp) { throw "Cannot proceed with existing temp zip" }
  Compress-Archive -Path (Join-Path $webhookDir '*') -DestinationPath $webhookZipTemp -Force
  aws lambda update-function-code --region $Region --function-name $WebhookFunction --zip-file fileb://$webhookZipTemp | Out-Null
  Write-Host "Deployed $WebhookFunction"
}

# Rebuild portfolio zip to temp path
$portfolioDir = "Project4-Swing-Automation-System/deployment/portfolio-lambda"
$portfolioZipTemp = New-TempZipPath "portfolio-reporter"
if (Test-Path $portfolioZipTemp) { Remove-Item $portfolioZipTemp -Force }
if (Test-Path $portfolioDir) {
  Compress-Archive -Path (Join-Path $portfolioDir '*') -DestinationPath $portfolioZipTemp -Force
  aws lambda update-function-code --region $Region --function-name $PortfolioFunction --zip-file fileb://$portfolioZipTemp | Out-Null
  Write-Host "Deployed $PortfolioFunction"
}