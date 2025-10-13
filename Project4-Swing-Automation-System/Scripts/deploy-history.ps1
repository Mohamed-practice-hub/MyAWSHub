param(
  [string]$Region = "us-east-1",
  [string]$FunctionName = "swing-history-api",
  [string]$RoleArn = "",
  [string]$Bucket = "swing-automation-data-processor",
  [string]$AlpacaSecret = "swing-alpaca/papter-trading/keys",
  [switch]$CreateFunctionUrl,
  [string]$SiteBucket = ""
)
$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/..\.." | Out-Null

function New-TempZipPath($name) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  return Join-Path $env:TEMP "$name-$stamp.zip"
}

$srcDir = "Project4-Swing-Automation-System/deployment/history-api"
if (-not (Test-Path $srcDir)) { throw "Source dir not found: $srcDir" }
$zipPath = New-TempZipPath "history-api"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $srcDir '*') -DestinationPath $zipPath -Force

# Try to update existing function, else create
$null = aws lambda get-function --region $Region --function-name $FunctionName 2>$null
$exists = ($LASTEXITCODE -eq 0)

if ($exists) {
  $null = aws lambda update-function-code --region $Region --function-name $FunctionName --zip-file fileb://$zipPath
  if ($LASTEXITCODE -ne 0) { throw "update-function-code failed" }
  Write-Host "Updated $FunctionName code"
  $envVars = 'Variables={ALPACA_TRADING_URL="https://paper-api.alpaca.markets",ALPACA_SECRET_NAME="' + $AlpacaSecret + '",S3_BUCKET="' + $Bucket + '"}'
  $null = aws lambda update-function-configuration --region $Region --function-name $FunctionName --environment $envVars
  if ($LASTEXITCODE -ne 0) { throw "update-function-configuration failed" }
} else {
  if (-not $RoleArn) { throw "RoleArn is required for create" }
  $envVars = 'Variables={ALPACA_TRADING_URL="https://paper-api.alpaca.markets",ALPACA_SECRET_NAME="' + $AlpacaSecret + '",S3_BUCKET="' + $Bucket + '"}'
  $null = aws lambda create-function --region $Region --function-name $FunctionName `
    --runtime python3.11 --handler history-api.lambda_handler `
    --role $RoleArn --timeout 30 --memory-size 256 `
    --zip-file fileb://$zipPath --environment $envVars
  if ($LASTEXITCODE -ne 0) { throw "create-function failed" }
  Write-Host "Created $FunctionName"
}

if ($CreateFunctionUrl) {
  # Create or update function URL with CORS
  $url = $null
  # Try get, else create
  $urlObj = aws lambda get-function-url-config --region $Region --function-name $FunctionName --output json 2>$null
  if ($LASTEXITCODE -eq 0) {
    $url = ($urlObj | ConvertFrom-Json).FunctionUrl
    Write-Host "Function URL exists: $url"
  } else {
    $cors = 'AllowOrigins=["*"],AllowMethods=["GET"],AllowHeaders=["*"],AllowCredentials=false'
    $createOut = aws lambda create-function-url-config --region $Region --function-name $FunctionName --auth-type NONE --cors $cors --output json
    if ($LASTEXITCODE -ne 0) { throw "create-function-url-config failed" }
    $url = ($createOut | ConvertFrom-Json).FunctionUrl
    Write-Host "Created Function URL: $url"
    $null = aws lambda add-permission --region $Region --function-name $FunctionName --statement-id "allow-public-url" --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE
  }
  Write-Host "History API URL: $url"
}

if ($SiteBucket) {
  $siteDir = "Project4-Swing-Automation-System/dashboard-site"
  if (Test-Path $siteDir) {
    aws s3 sync $siteDir s3://$SiteBucket/ --delete --cache-control no-cache | Out-Null
    Write-Host "Uploaded dashboard site to s3://$SiteBucket/"
  } else { Write-Host "Site dir not found: $siteDir" }
}
