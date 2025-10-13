# Project 3: Child Care Form Automation - Manual Setup Steps

## 💰 Cost Overview

### Monthly Cost Estimates (us-east-1):
- **SNS Email**: $0 (free)
- **Lambda**: Free tier 1M requests + 400K GB-seconds (likely $0)
- **API Gateway**: Free tier 1M requests (likely $0)
- **Total**: ~$0/month (completely free!)

## Step 1: Create SNS Topic
```bash
aws sns create-topic --name project3-childcare-sms --region us-east-1
```

## Step 2: Subscribe Email to SNS
```bash
aws sns subscribe --topic-arn arn:aws:sns:us-east-1:206055866143:project3-childcare-sms --protocol email --notification-endpoint mhussain.myindia@gmail.com --region us-east-1
```
**Note**: Check your email and confirm the subscription!

## Step 3: Create IAM Role for Lambda

### Bash/PowerShell (copy and run):
```bash
cd "c:\workarea\AWS Practice Projects\Mohamed-aws-portfolio-projects\Project3-Child-Care-Form-Automation"
aws iam create-role --role-name project3-lambda-role --assume-role-policy-document file://Security/trust-policy.json --region us-east-1
aws iam attach-role-policy --role-name project3-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region us-east-1
aws iam put-role-policy --role-name project3-lambda-role --policy-name SNSPublishPolicy --policy-document file://Security/sns-policy.json --region us-east-1
```

## Step 4: Create Lambda Function

### Option A: Git Bash (MINGW64)
```bash
cd "c:\workarea\AWS Practice Projects\Mohamed-aws-portfolio-projects\Project3-Child-Care-Form-Automation"
powershell "Compress-Archive Lambda/lambda_function.py lambda_function.zip -Force"
aws lambda create-function --function-name project3-childcare-processor --runtime python3.9 --role arn:aws:iam::206055866143:role/project3-lambda-role --handler lambda_function.lambda_handler --zip-file fileb://lambda_function.zip --timeout 10 --memory-size 128 --region us-east-1
```

### Option B: PowerShell
```powershell
cd "c:\workarea\AWS Practice Projects\Mohamed-aws-portfolio-projects\Project3-Child-Care-Form-Automation"
Compress-Archive Lambda/lambda_function.py lambda_function.zip -Force
aws lambda create-function --function-name project3-childcare-processor --runtime python3.9 --role arn:aws:iam::206055866143:role/project3-lambda-role --handler lambda_function.lambda_handler --zip-file fileb://lambda_function.zip --timeout 10 --memory-size 128 --region us-east-1
```

## Step 5: Create API Gateway

```bash
# Create REST API and get API_ID
aws apigateway create-rest-api --name project3-childcare-api --region us-east-1 --query 'id' --output text

# Copy the API_ID from above output, then get root resource ID
aws apigateway get-resources --rest-api-id wbmyjwq1m3 --region us-east-1 --query 'items[0].id' --output text

# Create resource
aws apigateway create-resource --rest-api-id wbmyjwq1m3 --parent-id 9cu04hybrf --path-part childcare --region us-east-1

# Create POST method
aws apigateway put-method --rest-api-id wbmyjwq1m3 --resource-id n3j4j1 --http-method POST --authorization-type NONE --region us-east-1

# Create OPTIONS method for CORS
aws apigateway put-method --rest-api-id wbmyjwq1m3 --resource-id n3j4j1 --http-method OPTIONS --authorization-type NONE --region us-east-1

# Set up Lambda integration for POST
aws apigateway put-integration --rest-api-id wbmyjwq1m3 --resource-id n3j4j1 --http-method POST --type AWS_PROXY --integration-http-method POST --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:206055866143:function:project3-childcare-processor/invocations --region us-east-1

# Set up CORS integration for OPTIONS
aws apigateway put-integration --rest-api-id wbmyjwq1m3 --resource-id n3j4j1 --http-method OPTIONS --type MOCK --request-templates '{"application/json":"{\"statusCode\": 200}"}' --region us-east-1

# Set up method response for OPTIONS (MUST come before integration response)
aws apigateway put-method-response --rest-api-id wbmyjwq1m3 --resource-id n3j4j1 --http-method OPTIONS --status-code 200 --response-parameters '{"method.response.header.Access-Control-Allow-Headers":true,"method.response.header.Access-Control-Allow-Methods":true,"method.response.header.Access-Control-Allow-Origin":true}' --region us-east-1

# Set up CORS integration response
aws apigateway put-integration-response --rest-api-id wbmyjwq1m3 --resource-id n3j4j1 --http-method OPTIONS --status-code 200 --response-parameters '{"method.response.header.Access-Control-Allow-Headers":"'"'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'"'","method.response.header.Access-Control-Allow-Methods":"'"'"'POST,OPTIONS'"'"'","method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}' --region us-east-1

# Deploy API
aws apigateway create-deployment --rest-api-id wbmyjwq1m3 --stage-name prod --region us-east-1
```

## Step 6: Grant API Gateway Permission to Lambda
```bash
aws lambda add-permission --function-name project3-childcare-processor --statement-id api-gateway-invoke --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:us-east-1:206055866143:wbmyjwq1m3/*/POST/childcare" --region us-east-1
```

## Step 7: Test the Setup

### API Endpoint:
`https://wbmyjwq1m3.execute-api.us-east-1.amazonaws.com/prod/childcare`

Test with:
```bash
curl -X POST https://wbmyjwq1m3.execute-api.us-east-1.amazonaws.com/prod/childcare -H "Content-Type: application/json" -d '{"name":"Test Child","date":"2024-01-15"}'
```

## 📊 Monitoring & Testing Commands

```bash
# Check Lambda log streams
aws logs describe-log-streams --log-group-name "/aws/lambda/project3-childcare-processor" --region us-east-1

# Check Lambda execution logs
aws logs get-log-events --log-group-name "/aws/lambda/project3-childcare-processor" --log-stream-name "STREAM_NAME_FROM_ABOVE" --region us-east-1

# Check SNS email delivery success
aws cloudwatch get-metric-statistics --namespace AWS/SNS --metric-name NumberOfMessagesSent --dimensions Name=TopicName,Value=project3-childcare-sms --start-time 2025-10-05T17:00:00Z --end-time 2025-10-05T19:00:00Z --period 300 --statistics Sum --region us-east-1

# Test email notification directly
aws sns publish --topic-arn arn:aws:sns:us-east-1:206055866143:project3-childcare-sms --message "Test email notification" --subject "Child Care Test" --region us-east-1

# Test complete API endpoint
curl -X POST https://wbmyjwq1m3.execute-api.us-east-1.amazonaws.com/prod/childcare -H "Content-Type: application/json" -d '{"name":"Emma Johnson","date":"2025-10-05"}'

# Test Lambda function directly
aws lambda invoke --function-name project3-childcare-processor --cli-binary-format raw-in-base64-out --payload '{"name":"Test Child","date":"2025-10-05"}' response.json --region us-east-1
```

## ✅ System Status: WORKING

**✅ Confirmed Working Components:**
- API Gateway: `https://wbmyjwq1m3.execute-api.us-east-1.amazonaws.com/prod/childcare`
- Lambda Function: Processing requests successfully
- SNS Email: Delivering to `mhussain.myindia@gmail.com`
- Cost: **$0/month** (completely free!)

**📧 Email Notifications:**
- Subject: "Daily Report - [Child Name]"
- Body: "Daily Report for [Child Name] - [Date]\n\nReport submitted successfully!"
- Delivery: Instant and reliable

**🔄 To Change Email Address:**
```bash
# Get current subscription ARN
aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:206055866143:project3-childcare-sms --region us-east-1

# Delete current email subscription
aws sns unsubscribe --subscription-arn "SUBSCRIPTION_ARN_FROM_ABOVE" --region us-east-1

# Add new email subscription
aws sns subscribe --topic-arn arn:aws:sns:us-east-1:206055866143:project3-childcare-sms --protocol email --notification-endpoint new-email@example.com --region us-east-1
```

## 🧹 Cleanup Commands (When Done)
```bash
# Get email subscription ARN first
aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:206055866143:project3-childcare-sms --region us-east-1

# Delete Lambda function
aws lambda delete-function --function-name project3-childcare-processor --region us-east-1

# Delete REST API
aws apigateway delete-rest-api --rest-api-id wbmyjwq1m3 --region us-east-1

# Delete IAM role policies and role
aws iam delete-role-policy --role-name project3-lambda-role --policy-name SNSPublishPolicy --region us-east-1
aws iam detach-role-policy --role-name project3-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region us-east-1
aws iam delete-role --role-name project3-lambda-role --region us-east-1

# Delete email subscription and topic
aws sns unsubscribe --subscription-arn "EMAIL_SUBSCRIPTION_ARN_FROM_ABOVE" --region us-east-1
aws sns delete-topic --topic-arn arn:aws:sns:us-east-1:206055866143:project3-childcare-sms --region us-east-1
```

---

## 🎉 Project Complete!

**Your Child Care Form Automation System is fully deployed and working!**

- **API Endpoint**: `https://wbmyjwq1m3.execute-api.us-east-1.amazonaws.com/prod/childcare`
- **Email Notifications**: `mhussain.myindia@gmail.com`
- **Monthly Cost**: $0 (Free tier)
- **Status**: ✅ Production Ready