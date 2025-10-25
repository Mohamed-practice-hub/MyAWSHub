# deploy-analysis-lambda.ps1
# Deploy the analysis Lambda on Windows PowerShell

$REGION = 'us-east-1'
$LAMBDA_NAME = 'tradebot-analysis-lambda'
$ROLE_ARN = 'arn:aws:iam::206055866143:role/tradebot-lambda-role'  # Update if needed
$ZIP_FILE = 'analysis_lambda.zip'
$HANDLER = 'analysis_lambda.lambda_handler'
$RUNTIME = 'python3.11'
$DDB_TABLE = 'tradebot_signals_table'

$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$lambdaFile = Join-Path $scriptDir 'analysis_lambda.py'
if (-not (Test-Path $lambdaFile)) {
  Write-Error "Lambda source file not found: $lambdaFile"
  exit 1
}

# Zip the lambda
if (Test-Path $ZIP_FILE) { Remove-Item $ZIP_FILE -Force }
Compress-Archive -Path $lambdaFile -DestinationPath $ZIP_FILE -Force
Write-Host "Packaged $lambdaFile -> $ZIP_FILE"

# Verify DynamoDB table exists and streams enabled
try {
  $desc = aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION --output json | ConvertFrom-Json
} catch {
  Write-Error "DynamoDB table $DDB_TABLE not found. Please create it first."
  exit 1
}

if (-not $desc.Table.LatestStreamArn) {
  Write-Host "Enabling stream on $DDB_TABLE..."
  aws dynamodb update-table --table-name $DDB_TABLE --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES --region $REGION
  Write-Host "Waiting for stream ARN to appear..."
  for ($i=0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    $desc = aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION --output json | ConvertFrom-Json
    if ($desc.Table.LatestStreamArn) { break }
  }
  if (-not $desc.Table.LatestStreamArn) { Write-Error "Stream ARN did not appear in time"; exit 1 }
}
$streamArn = $desc.Table.LatestStreamArn
Write-Host "Table stream ARN: $streamArn"

# Create or update the Lambda function
aws lambda get-function --function-name $LAMBDA_NAME --region $REGION > $null 2>&1
if ($LASTEXITCODE -eq 0) {
  Write-Host "Updating Lambda code..."
  aws lambda update-function-code --function-name $LAMBDA_NAME --zip-file fileb://$ZIP_FILE --region $REGION
  Write-Host "Updating Lambda configuration (env)..."
  aws lambda update-function-configuration --function-name $LAMBDA_NAME --environment "Variables={DYNAMODB_TABLE=$DDB_TABLE}" --region $REGION
} else {
  Write-Host "Creating Lambda function..."
  aws lambda create-function --function-name $LAMBDA_NAME --runtime $RUNTIME --role $ROLE_ARN --handler $HANDLER --zip-file fileb://$ZIP_FILE --timeout 30 --memory-size 256 --environment "Variables={DYNAMODB_TABLE=$DDB_TABLE}" --region $REGION
}

# Create event source mapping
$existing = aws lambda list-event-source-mappings --function-name $LAMBDA_NAME --region $REGION --query "EventSourceMappings[?EventSourceArn=='$streamArn'].UUID" --output text
if (-not $existing) {
  aws lambda create-event-source-mapping --function-name $LAMBDA_NAME --event-source-arn $streamArn --starting-position LATEST --batch-size 100 --region $REGION
  Write-Host "Created event source mapping"
} else {
  Write-Host "Event source mapping already exists: $existing"
}

# Clean up
Remove-Item $ZIP_FILE -Force
Write-Host "Analysis Lambda deployed successfully."