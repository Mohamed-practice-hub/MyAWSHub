#!/bin/bash
set -e

# Deploy DynamoDB Stream exporter Lambda
LAMBDA_NAME="dynamo-stream-exporter"
ROLE_ARN="arn:aws:iam::206055866143:role/tradebot-lambda-role" # Update to your lambda role that has S3 and DynamoDB Stream access
ZIP_FILE="dynamo_stream_exporter.zip"
HANDLER="dynamodb_stream_to_s3.lambda_handler"
RUNTIME="python3.11"
REGION="us-east-1"
DDB_TABLE="tradebot_signals_table"
S3_BUCKET="tradebot-206055866143-dashboard"
S3_KEY="data.json"

cd lambda
zip -j ../$ZIP_FILE dynamodb_stream_to_s3.py
cd ..

if aws lambda get-function --function-name $LAMBDA_NAME --region $REGION >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $LAMBDA_NAME --zip-file fileb://$ZIP_FILE --region $REGION
else
  aws lambda create-function --function-name $LAMBDA_NAME --runtime $RUNTIME --role $ROLE_ARN --handler $HANDLER --zip-file fileb://$ZIP_FILE --timeout 30 --memory-size 256 --environment "Variables={DDB_TABLE=$DDB_TABLE,S3_BUCKET=$S3_BUCKET,S3_KEY=$S3_KEY}" --region $REGION
fi

# Enable stream on the DynamoDB table and create event source mapping
# Assumes the table has streams enabled already. Otherwise enable it in the Console or via CLI with StreamSpecification.
TABLE_ARN=$(aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION --query 'Table.LatestStreamArn' --output text)
if [ "$TABLE_ARN" = "None" ]; then
  echo "DynamoDB table streaming not enabled. Please enable DynamoDB Streams on the table with NEW_AND_OLD_IMAGES and re-run."
  exit 1
fi

# Create event source mapping
ESM=$(aws lambda list-event-source-mappings --function-name $LAMBDA_NAME --region $REGION --query 'EventSourceMappings[?EventSourceArn==`'$TABLE_ARN'`].UUID' --output text)
if [ -z "$ESM" ]; then
  aws lambda create-event-source-mapping --function-name $LAMBDA_NAME --event-source-arn $TABLE_ARN --starting-position LATEST --batch-size 100 --region $REGION
  echo "Created event source mapping for $TABLE_ARN"
else
  echo "Event source mapping already exists: $ESM"
fi

# Cleanup
rm -f $ZIP_FILE

echo "Done. Exporter Lambda deployed."
