param(
    [string]$Region = "us-east-1",
    [string]$FunctionName = "tradebot_fetch_lambda",
    [string]$RoleName = "tradebot-lambda-role"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LambdaPath = Join-Path $ScriptDir "fetch_lambda.py"
$ZipPath = Join-Path $ScriptDir "fetch_lambda.zip"

# Clean up old zip
if (Test-Path $ZipPath) { Remove-Item $ZipPath }

# Package Lambda (assumes dependencies are vendored or layer is used)
Compress-Archive -Path $LambdaPath -DestinationPath $ZipPath

# Try to get the role ARN
$role = $null
try {
    $role = (aws iam get-role --role-name $RoleName --region $Region | ConvertFrom-Json).Role.Arn
} catch {
    Write-Host "ERROR: IAM role '$RoleName' not found in region $Region. Please create the role and try again."
    exit 1
}

# Check if function exists
$exists = $false
try {
    aws lambda get-function --function-name $FunctionName --region $Region | Out-Null
    $exists = $true
} catch {}

if (-not $exists) {
    aws lambda create-function `
        --function-name $FunctionName `
        --runtime python3.11 `
        --role $role `
        --handler fetch_lambda.lambda_handler `
        --zip-file fileb://$ZipPath `
        --timeout 300 `
        --memory-size 256 `
        --region $Region
} else {
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file fileb://$ZipPath `
        --region $Region
}

Write-Host "Deployed $FunctionName to $Region."
