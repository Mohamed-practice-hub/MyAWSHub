#!/bin/bash
# Deploy the fetch_lambda Lambda function using AWS CLI
echo "Deployed $LAMBDA_NAME to $REGION."
#!/bin/bash
set -e

LAMBDA_NAME="tradebot_fetch_lambda"
ROLE_ARN="arn:aws:iam::206055866143:role/tradebot-lambda-role"
ZIP_FILE="fetch_lambda.zip"
HANDLER="fetch_lambda.lambda_handler"
RUNTIME="python3.11"
REGION="us-east-1"

echo "Packaging Lambda code..."
powershell.exe -Command "Compress-Archive -Path fetch_lambda.py -DestinationPath fetch_lambda.zip -Force"

echo "Deploying Lambda function..."
if aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" >/dev/null 2>&1; then
    aws lambda update-function-code \
        --function-name "$LAMBDA_NAME" \
        --zip-file fileb://$ZIP_FILE \
        --region "$REGION"
else
    aws lambda create-function \
        --function-name "$LAMBDA_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file fileb://$ZIP_FILE \
        --timeout 300 \
        --memory-size 256 \
        --region "$REGION"
fi

echo "Cleaning up..."
rm -f fetch_lambda.zip

echo "✅ Lambda deployment complete."
