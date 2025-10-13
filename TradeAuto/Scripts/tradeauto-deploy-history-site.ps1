param(
  [string]$Region = "us-east-1",
  [string]$BucketName = ""
)
$ErrorActionPreference = 'Stop'

$sts = aws sts get-caller-identity | ConvertFrom-Json
$accountId = $sts.Account
if(-not $BucketName){ $BucketName = "tradeauto-automation-data-$accountId-$Region" }

$sitePrefix = 'site/history-dashboard/'
$siteDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'web' 'history-dashboard'

aws s3 sync $siteDir "s3://$BucketName/$sitePrefix" --delete

Write-Host "Uploaded site to s3://$BucketName/$sitePrefix"
