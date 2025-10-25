#!/bin/bash
aws lambda invoke \
  --function-name tradebot_fetch_lambda \
  --region us-east-1 \
  --payload fileb://fetch_lambda_test.json \
  --cli-binary-format raw-in-base64-out \
  fetch_lambda_output.json
