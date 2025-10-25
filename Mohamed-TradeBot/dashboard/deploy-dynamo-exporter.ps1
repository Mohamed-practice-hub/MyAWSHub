<#
deploy-dynamo-exporter.ps1

Deploy the DynamoDB Stream -> S3 exporter Lambda on Windows (PowerShell).

Edit variables below to match your environment.
#>

$REGION = 'us-east-1'
$LAMBDA_NAME = 'dynamo-stream-exporter'
$ROLE_ARN = 'arn:aws:iam::206055866143:role/tradebot-lambda-role' # update if needed
$ZIP_FILE = 'dynamo_stream_exporter.zip'
$HANDLER = 'dynamodb_stream_to_s3.lambda_handler'
$RUNTIME = 'python3.11'
$DDB_TABLE = 'tradebot_signals_table'
$S3_BUCKET = 'tradebot-206055866143-dashboard'
$S3_KEY = 'data.json'

# Determine script and lambda paths
$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$lambdaFile = Join-Path $scriptDir 'lambda\dynamodb_stream_to_s3.py'
if (-not (Test-Path $lambdaFile)) {
  Write-Error "Lambda source file not found: $lambdaFile"
  exit 1
}

# Zip the lambda file (ensure the python file is at the root of the zip)
if (Test-Path $ZIP_FILE) { Remove-Item $ZIP_FILE -Force }
Compress-Archive -Path $lambdaFile -DestinationPath $ZIP_FILE -Force
Write-Host "Packaged $lambdaFile -> $ZIP_FILE"

# Verify DynamoDB table exists before attempting to create lambda
try {
  aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION > $null 2>&1
} catch {
  Write-Error "DynamoDB table $DDB_TABLE not found. Please create it or set DDB_TABLE to the correct table name."
  exit 1
}

# Create or update lambda: detect existence by CLI exit code
$exists = $false
aws lambda get-function --function-name $LAMBDA_NAME --region $REGION > $null 2>&1
if ($LASTEXITCODE -eq 0) {
  $exists = $true
}

if ($exists) {
  Write-Host "Updating Lambda code..."
  aws lambda update-function-code --function-name $LAMBDA_NAME --zip-file fileb://$ZIP_FILE --region $REGION
  Write-Host "Updating Lambda configuration (env vars)..."
  aws lambda update-function-configuration --function-name $LAMBDA_NAME --environment "Variables={DDB_TABLE=$DDB_TABLE,S3_BUCKET=$S3_BUCKET,S3_KEY=$S3_KEY}" --region $REGION
} else {
  Write-Host "Creating Lambda function..."
  aws lambda create-function --function-name $LAMBDA_NAME --runtime $RUNTIME --role $ROLE_ARN --handler $HANDLER --zip-file fileb://$ZIP_FILE --timeout 30 --memory-size 256 --environment "Variables={DDB_TABLE=$DDB_TABLE,S3_BUCKET=$S3_BUCKET,S3_KEY=$S3_KEY}" --region $REGION
}

# Get the stream ARN for the table
$streamArn = aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION --query 'Table.LatestStreamArn' --output text
if ($streamArn -eq 'None' -or [string]::IsNullOrEmpty($streamArn)) {
  Write-Error "DynamoDB Streams not enabled for table $DDB_TABLE. Enable Streams (NEW_AND_OLD_IMAGES) and retry."
  exit 1
}
Write-Host "Table stream ARN: $streamArn"

# Create event source mapping if not exists
$existing = aws lambda list-event-source-mappings --function-name $LAMBDA_NAME --region $REGION --query "EventSourceMappings[?EventSourceArn=='$streamArn'].UUID" --output text
if (-not $existing) {
  aws lambda create-event-source-mapping --function-name $LAMBDA_NAME --event-source-arn $streamArn --starting-position LATEST --batch-size 100 --region $REGION
  Write-Host "Created event source mapping"
} else {
  Write-Host "Event source mapping already exists: $existing"
}

# Cleanup local zip
Remove-Item $ZIP_FILE -Force

Write-Host "Deployment completed. The Lambda will write snapshots to s3://$S3_BUCKET/$S3_KEY on stream events."
