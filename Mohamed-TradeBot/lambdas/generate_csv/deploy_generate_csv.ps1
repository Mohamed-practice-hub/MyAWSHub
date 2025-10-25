param(
  [string]$FunctionName = 'tradebot-generate-csv',
  [string]$RoleArn = 'arn:aws:iam::206055866143:role/tradebot-lambda-role',
  [string]$Region = 'us-east-1'
)

Set-Location $PSScriptRoot
if(Test-Path .\deploy_package.zip){ Remove-Item .\deploy_package.zip }
Compress-Archive -Path .\* -DestinationPath .\deploy_package.zip -Force

# Check if function exists
$exists = aws lambda get-function-configuration --function-name $FunctionName --region $Region 2>$null
if($LASTEXITCODE -eq 0) {
  Write-Host 'Updating existing function code...'
  aws lambda update-function-code --function-name $FunctionName --zip-file fileb://./deploy_package.zip --region $Region
} else {
  Write-Host 'Creating new Lambda function...'
  aws lambda create-function --function-name $FunctionName --zip-file fileb://./deploy_package.zip --runtime python3.11 --role $RoleArn --handler generate_csv.lambda_handler --timeout 300 --memory-size 512 --region $Region
}

Write-Host 'Done. Remember to set environment variables S3_BUCKET and DYNAMODB_TABLE for the function.'
