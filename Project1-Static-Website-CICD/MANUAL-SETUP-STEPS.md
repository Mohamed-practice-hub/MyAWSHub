# Project 1: Static Website with CI/CD Pipeline - Manual Setup Steps

## 💰 Cost Overview

### Monthly Cost Estimates (us-east-1):
- **S3**: $0.023 per GB/month (likely $0-1/month)
- **CloudFront**: $0.085 per GB + $0.0075 per 10,000 requests (likely $1-5/month)
- **Lambda**: Free tier 1M requests + 400K GB-seconds (likely $0)
- **CodePipeline**: $1/month per active pipeline
- **CodeBuild**: $0.005 per build minute (likely $0-2/month)
- **Route 53**: $0.50 per hosted zone/month (optional)
- **Certificate Manager**: Free for AWS resources
- **Total**: ~$2-10/month depending on traffic

## Step 1: Create S3 Bucket for Website
```bash
# Create S3 bucket (must be globally unique)
aws s3 mb s3://my-static-website-bucket --region us-east-1

# Enable static website hosting
aws s3 website s3://my-static-website-bucket --index-document index.html --error-document error.html --region us-east-1

# Upload website files
cd "c:\workarea\AWS Practice Projects\Mohamed-aws-portfolio-projects\Project1-Static-Website-CICD"
aws s3 sync Forms/ s3://my-static-website-bucket --region us-east-1
aws s3 cp Scripts/styles.css s3://my-static-website-bucket/styles.css --region us-east-1
```

## Step 2: Create S3 Bucket Policy for Public Access
```bash
# Create bucket policy file
echo '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-static-website-bucket/*"
    }
  ]
}' > bucket-policy.json

# Apply bucket policy
aws s3api put-bucket-policy --bucket my-static-website-bucket --policy file://bucket-policy.json --region us-east-1

# Disable block public access
aws s3api put-public-access-block --bucket my-static-website-bucket --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" --region us-east-1
```

## Step 3: Create CloudFront Distribution
```bash
# Create CloudFront distribution configuration
echo '{
  "CallerReference": "static-website-'$(date +%s)'",
  "Comment": "Static website distribution",
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-my-static-website-bucket",
        "DomainName": "my-static-website-bucket.s3.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": ""
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-my-static-website-bucket",
    "ViewerProtocolPolicy": "redirect-to-https",
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {
        "Forward": "none"
      }
    },
    "MinTTL": 0
  },
  "Enabled": true,
  "PriceClass": "PriceClass_100"
}' > cloudfront-config.json

# Create CloudFront distribution
aws cloudfront create-distribution --distribution-config file://cloudfront-config.json --region us-east-1
```

## Step 4: Create IAM Role for Lambda
```bash
# Create trust policy for Lambda
echo '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}' > lambda-trust-policy.json

# Create IAM role
aws iam create-role --role-name static-website-lambda-role --assume-role-policy-document file://lambda-trust-policy.json --region us-east-1

# Attach basic execution policy
aws iam attach-role-policy --role-name static-website-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region us-east-1

# Attach SES policy
aws iam put-role-policy --role-name static-website-lambda-role --policy-name SESPolicy --policy-document file://Security/ses-lambda-permission.json --region us-east-1
```

## Step 5: Create Lambda Function for Contact Form
```bash
# Create deployment package
powershell "Compress-Archive Lambda/lambda-form.py contact-form-lambda.zip -Force"

# Create Lambda function
aws lambda create-function --function-name ContactFormProcessor --runtime python3.9 --role arn:aws:iam::ACCOUNT_ID:role/static-website-lambda-role --handler lambda-form.lambda_handler --zip-file fileb://contact-form-lambda.zip --timeout 30 --memory-size 256 --region us-east-1
```

## Step 6: Create API Gateway for Contact Form
```bash
# Create REST API
aws apigateway create-rest-api --name contact-form-api --region us-east-1 --query 'id' --output text

# Get root resource ID (replace API_ID with actual ID)
aws apigateway get-resources --rest-api-id API_ID --region us-east-1 --query 'items[0].id' --output text

# Create contact resource
aws apigateway create-resource --rest-api-id API_ID --parent-id ROOT_RESOURCE_ID --path-part contact --region us-east-1

# Create POST method
aws apigateway put-method --rest-api-id API_ID --resource-id CONTACT_RESOURCE_ID --http-method POST --authorization-type NONE --region us-east-1

# Set up Lambda integration
aws apigateway put-integration --rest-api-id API_ID --resource-id CONTACT_RESOURCE_ID --http-method POST --type AWS_PROXY --integration-http-method POST --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:ACCOUNT_ID:function:ContactFormProcessor/invocations --region us-east-1

# Deploy API
aws apigateway create-deployment --rest-api-id API_ID --stage-name prod --region us-east-1
```

## Step 7: Create CodePipeline for CI/CD
```bash
# Create CodePipeline service role
aws iam create-role --role-name CodePipelineServiceRole --assume-role-policy-document file://Security/codepipeline-role-perm.json --region us-east-1

# Create S3 bucket for pipeline artifacts
aws s3 mb s3://codepipeline-artifacts-bucket --region us-east-1

# Create CodeBuild project
aws codebuild create-project --name static-website-build --source type=CODEPIPELINE,buildspec=buildspec.yml --artifacts type=CODEPIPELINE --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:5.0,computeType=BUILD_GENERAL1_SMALL --service-role arn:aws:iam::ACCOUNT_ID:role/CodePipelineServiceRole --region us-east-1
```

## Step 8: Verify SES Email Address
```bash
# Verify sender email address
aws ses verify-email-identity --email-address your-email@example.com --region us-east-1

# Check verification status
aws ses get-identity-verification-attributes --identities your-email@example.com --region us-east-1
```

## Step 9: Test the Setup

### Website URL:
`http://my-static-website-bucket.s3-website-us-east-1.amazonaws.com`

### CloudFront URL:
`https://DISTRIBUTION_ID.cloudfront.net`

### API Endpoint:
`https://API_ID.execute-api.us-east-1.amazonaws.com/prod/contact`

Test contact form:
```bash
curl -X POST https://API_ID.execute-api.us-east-1.amazonaws.com/prod/contact -H "Content-Type: application/json" -d '{"name":"Test User","email":"test@example.com","message":"Test message"}'
```

## 📊 Monitoring Commands

```bash
# Check Lambda logs
aws logs describe-log-streams --log-group-name "/aws/lambda/ContactFormProcessor" --region us-east-1

# Check CloudFront distribution status
aws cloudfront get-distribution --id DISTRIBUTION_ID --region us-east-1

# Check CodePipeline status
aws codepipeline get-pipeline-state --name PIPELINE_NAME --region us-east-1

# Check S3 website configuration
aws s3api get-bucket-website --bucket my-static-website-bucket --region us-east-1
```

## 🧹 Cleanup Commands
```bash
# Delete Lambda function
aws lambda delete-function --function-name ContactFormProcessor --region us-east-1

# Delete API Gateway
aws apigateway delete-rest-api --rest-api-id API_ID --region us-east-1

# Delete CloudFront distribution (must disable first)
aws cloudfront get-distribution-config --id DISTRIBUTION_ID --region us-east-1
# Edit config to set Enabled=false, then update
aws cloudfront update-distribution --id DISTRIBUTION_ID --distribution-config file://updated-config.json --if-match ETAG --region us-east-1
aws cloudfront delete-distribution --id DISTRIBUTION_ID --if-match ETAG --region us-east-1

# Delete S3 buckets
aws s3 rb s3://my-static-website-bucket --force --region us-east-1
aws s3 rb s3://codepipeline-artifacts-bucket --force --region us-east-1

# Delete IAM roles
aws iam delete-role-policy --role-name static-website-lambda-role --policy-name SESPolicy --region us-east-1
aws iam detach-role-policy --role-name static-website-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole --region us-east-1
aws iam delete-role --role-name static-website-lambda-role --region us-east-1
```

**Note**: Replace API_ID, ACCOUNT_ID, DISTRIBUTION_ID, and other placeholders with actual values from command outputs.