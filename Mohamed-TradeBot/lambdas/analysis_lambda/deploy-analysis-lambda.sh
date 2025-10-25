#!/bin/bash
set -e

LAMBDA_NAME="tradebot-analysis-lambda"
ROLE_ARN="arn:aws:iam::206055866143:role/tradebot-lambda-role"
ZIP_FILE="analysis_lambda.zip"
HANDLER="analysis_lambda.lambda_handler"
RUNTIME="python3.11"
REGION="us-east-1"
DDB_TABLE="tradebot_signals_table"

cd $(dirname "$0")
zip -j ../$ZIP_FILE analysis_lambda.py
cd ..

if aws lambda get-function --function-name $LAMBDA_NAME --region $REGION >/dev/null 2>&1; then
  echo "Updating Lambda code..."
  aws lambda update-function-code --function-name $LAMBDA_NAME --zip-file fileb://$ZIP_FILE --region $REGION
else
  echo "Creating Lambda..."
  aws lambda create-function --function-name $LAMBDA_NAME --runtime $RUNTIME --role $ROLE_ARN --handler $HANDLER --zip-file fileb://$ZIP_FILE --timeout 30 --memory-size 256 --environment "Variables={DYNAMODB_TABLE=$DDB_TABLE}" --region $REGION
fi

# Create event source mapping from DynamoDB stream to this lambda
TABLE_ARN=$(aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION --query 'Table.LatestStreamArn' --output text)
if [ "$TABLE_ARN" = "None" ]; then
  echo "DynamoDB streams not enabled for $DDB_TABLE; enable streams and retry"
  exit 1
fi

# Create mapping if not exists
ESM=$(aws lambda list-event-source-mappings --function-name $LAMBDA_NAME --region $REGION --query "EventSourceMappings[?EventSourceArn==''$TABLE_ARN''].UUID" --output text)
if [ -z "$ESM" ]; then
  aws lambda create-event-source-mapping --function-name $LAMBDA_NAME --event-source-arn $TABLE_ARN --starting-position LATEST --batch-size 100 --region $REGION
  echo "Event source mapping created"
else
  echo "Event source mapping exists: $ESM"
fi

rm -f $ZIP_FILE

echo "Analysis Lambda deployed."