#!/bin/bash
set -e

# Deploy dashboard API Lambda and an HTTP API Gateway v2 (public endpoint)
API_NAME="tradebot-dashboard-api-v1"
LAMBDA_NAME="tradebot_dashboard_api_v1"
ROLE_ARN="arn:aws:iam::206055866143:role/tradebot-lambda-role"
ZIP_FILE="dynamodb_api_v1.zip"
HANDLER="dynamodb_api_v1.lambda_handler"
RUNTIME="python3.11"
REGION="us-east-1"
DDB_TABLE="tradebot_table"

# Package the lambda
echo "Packaging Lambda..."
zip -j "$ZIP_FILE" lambda/dynamodb_api_v1.py

# Create or update lambda
if aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Updating Lambda code..."
  aws lambda update-function-code --function-name "$LAMBDA_NAME" --zip-file fileb://$ZIP_FILE --region $REGION
else
  echo "Creating Lambda..."
  aws lambda create-function --function-name "$LAMBDA_NAME" --runtime "$RUNTIME" --role "$ROLE_ARN" --handler "$HANDLER" --zip-file fileb://$ZIP_FILE --timeout 30 --memory-size 256 --environment "Variables={DDB_TABLE=$DDB_TABLE}" --region $REGION
fi

# Create an HTTP API with a default route and integration if not exists
API_ID=$(aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='$API_NAME'].ApiId" --output text || echo "")
if [ -z "$API_ID" ]; then
  echo "Creating HTTP API..."
  API_ID=$(aws apigatewayv2 create-api --name "$API_NAME" --protocol-type HTTP --region $REGION --query ApiId --output text)
fi

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id $API_ID --region $REGION --query "Items[?IntegrationType=='AWS_PROXY' && contains(IntegrationUri, '$LAMBDA_NAME')].IntegrationId" --output text || echo "")
if [ -z "$INTEGRATION_ID" ]; then
  echo "Creating integration..."
  LAMBDA_ARN=$(aws lambda get-function --function-name $LAMBDA_NAME --region $REGION --query 'Configuration.FunctionArn' --output text)
  INTEGRATION_ID=$(aws apigatewayv2 create-integration --api-id $API_ID --integration-type AWS_PROXY --integration-uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" --payload-format-version 2.0 --region $REGION --query IntegrationId --output text)
fi

# Create route and deployment
ROUTE_ID=$(aws apigatewayv2 get-routes --api-id $API_ID --region $REGION --query "Items[?RouteKey=='GET /table'].RouteId" --output text || echo "")
if [ -z "$ROUTE_ID" ]; then
  aws apigatewayv2 create-route --api-id $API_ID --route-key "GET /table" --target "integrations/$INTEGRATION_ID" --region $REGION
fi

# Grant permission for APIGW to invoke Lambda
PRINCIPAL="apigateway.amazonaws.com"
STATEMENT_ID="apigw-invoke-$API_ID"
aws lambda add-permission --function-name $LAMBDA_NAME --statement-id $STATEMENT_ID --action lambda:InvokeFunction --principal $PRINCIPAL --region $REGION || true

# Create stage
STAGE_NAME="prod"
aws apigatewayv2 create-deployment --api-id $API_ID --region $REGION >/dev/null || true
aws apigatewayv2 create-stage --api-id $API_ID --stage-name $STAGE_NAME --auto-deploy --region $REGION || true

API_ENDPOINT="https://$API_ID.execute-api.$REGION.amazonaws.com/$STAGE_NAME/table"

# Output the endpoint
echo "API endpoint: $API_ENDPOINT"

echo "Cleaning up..."
rm -f "$ZIP_FILE"

# Done
