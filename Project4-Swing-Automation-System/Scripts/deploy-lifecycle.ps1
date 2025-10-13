param(
  [string]$Region = "us-east-1",
  [string]$Bucket = "swing-automation-data-processor"
)
$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/..\.." | Out-Null
$file = Resolve-Path "Project4-Swing-Automation-System/deployment/s3-lifecycle-rules.json"
aws s3api put-bucket-lifecycle-configuration --bucket $Bucket --lifecycle-configuration ("file://" + $file)
if ($LASTEXITCODE -ne 0) { throw "put-bucket-lifecycle-configuration failed ($LASTEXITCODE)" }
Write-Host "Applied lifecycle to $Bucket"