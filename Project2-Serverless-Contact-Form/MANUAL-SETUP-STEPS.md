# Project 2: Serverless Contact Form - Manual Setup Steps

## 💰 Cost Overview

### Monthly Cost Estimates (us-east-1):
- **SES**: $0.10 per 1,000 emails (likely $0-1/month)
- **Lambda**: Free tier 1M requests + 400K GB-seconds (likely $0)
- **API Gateway**: Free tier 1M requests (likely $0)
- **S3**: $0.023 per GB/month (likely $0-1/month)
- **Total**: ~$0-2/month

## Step 1: Create S3 Bucket for Form Data
```bash
aws s3 mb s3://contact-form-data-bucket --region us-east-1
```

## Step 2: Create IAM Role for Lambda
```bash
cd "c:\workarea\AWS Practice Projects\Mohamed-aws-portfolio-projects\Project2-Serverless-Contact-Form"
aws iam create-role --role-name contact-form-lambda-role --assume-role-policy-document file://Security/lambda-trust-policy.json --region us-east-1
aws iam attach-role-policy --role-name contact-form-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region us-east-1
aws iam put-role-policy --role-name contact-form-lambda-role --policy-name SESPolicy --policy-document file://Security/ses-lambda-policy.json --region us-east-1
```

## Step 3: Verify SES Email Address
```bash
# Verify sender email address
aws ses verify-email-identity --email-address your-email@example.com --region us-east-1

# Check verification status
aws ses get-identity-verification-attributes --identities your-email@example.com --region us-east-1
```

## Step 4: Create Lambda Function
```bash
# Create deployment package
powershell "Compress-Archive Lambda/ProcessContactForm.py contact-form.zip -Force"

# Create Lambda function
aws lambda create-function --function-name ProcessContactForm --runtime python3.9 --role arn:aws:iam::ACCOUNT_ID:role/contact-form-lambda-role --handler ProcessContactForm.lambda_handler --zip-file fileb://contact-form.zip --timeout 30 --memory-size 256 --region us-east-1
```

## Step 5: Create API Gateway
```bash
# Create REST API
aws apigateway create-rest-api --name contact-form-api --region us-east-1 --query 'id' --output text

# Get root resource ID (replace API_ID with actual ID from above)
aws apigateway get-resources --rest-api-id API_ID --region us-east-1 --query 'items[0].id' --output text

# Create contact resource
aws apigateway create-resource --rest-api-id API_ID --parent-id ROOT_RESOURCE_ID --path-part contact --region us-east-1

# Create POST method
aws apigateway put-method --rest-api-id API_ID --resource-id CONTACT_RESOURCE_ID --http-method POST --authorization-type NONE --region us-east-1

# Set up Lambda integration
aws apigateway put-integration --rest-api-id API_ID --resource-id CONTACT_RESOURCE_ID --http-method POST --type AWS_PROXY --integration-http-method POST --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:ACCOUNT_ID:function:ProcessContactForm/invocations --region us-east-1

# Deploy API
aws apigateway create-deployment --rest-api-id API_ID --stage-name prod --region us-east-1
```

## Step 6: Grant API Gateway Permission to Lambda
```bash
aws lambda add-permission --function-name ProcessContactForm --statement-id api-gateway-invoke --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:us-east-1:ACCOUNT_ID:API_ID/*/POST/contact" --region us-east-1
```

## Step 7: Upload Contact Form to S3
```bash
# Create S3 bucket for hosting
aws s3 mb s3://contact-form-website --region us-east-1

# Upload contact form
aws s3 cp Forms/contact.html s3://contact-form-website/contact.html --acl public-read --region us-east-1

# Enable static website hosting
aws s3 website s3://contact-form-website --index-document contact.html --region us-east-1
```

## Step 8: Configure CORS (if needed)
```bash
# Create CORS configuration file
echo '{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "POST"],
      "MaxAgeSeconds": 3000
    }
  ]
}' > cors-config.json

# Apply CORS configuration
aws s3api put-bucket-cors --bucket contact-form-website --cors-configuration file://cors-config.json --region us-east-1
```

## Step 9: Test the Setup

### API Endpoint:
`https://API_ID.execute-api.us-east-1.amazonaws.com/prod/contact`

### Website URL:
`http://contact-form-website.s3-website-us-east-1.amazonaws.com`

Test with:
```bash
curl -X POST https://API_ID.execute-api.us-east-1.amazonaws.com/prod/contact -H "Content-Type: application/json" -d '{"name":"Test User","email":"test@example.com","message":"Test message"}'
```

## 📊 Monitoring Commands

```bash
# Check Lambda logs
aws logs describe-log-streams --log-group-name "/aws/lambda/ProcessContactForm" --region us-east-1

# Check SES sending statistics
aws ses get-send-statistics --region us-east-1

# Test Lambda function directly
aws lambda invoke --function-name ProcessContactForm --cli-binary-format raw-in-base64-out --payload file://Security/lambda-test-direct.json response.json --region us-east-1
```

## 🧹 Cleanup Commands
```bash
# Delete Lambda function
aws lambda delete-function --function-name ProcessContactForm --region us-east-1

# Delete API Gateway
aws apigateway delete-rest-api --rest-api-id API_ID --region us-east-1

# Delete IAM role
aws iam delete-role-policy --role-name contact-form-lambda-role --policy-name SESPolicy --region us-east-1
aws iam detach-role-policy --role-name contact-form-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region us-east-1
aws iam delete-role --role-name contact-form-lambda-role --region us-east-1

# Delete S3 buckets
aws s3 rb s3://contact-form-website --force --region us-east-1
aws s3 rb s3://contact-form-data-bucket --force --region us-east-1
```

**Note**: Replace API_ID, ACCOUNT_ID, ROOT_RESOURCE_ID, and CONTACT_RESOURCE_ID with actual values from command outputs.