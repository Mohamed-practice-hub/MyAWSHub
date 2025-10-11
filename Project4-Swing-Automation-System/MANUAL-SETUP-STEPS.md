# AWS Swing Trading Automation System - Manual Setup Guide

## Overview
Complete step-by-step manual setup guide for the AWS Swing Trading Automation System using RSI and EMA indicators.

## Prerequisites
- AWS Account with appropriate permissions
- AWS CLI configured
- Git Bash terminal (for Windows users)

## Architecture Components
- **Lambda Functions**: Main trading bot + Performance analyzer
- **S3 Bucket**: Data storage for analysis and signals
- **EventBridge**: Scheduled execution (daily + weekly)
- **Secrets Manager**: Secure API key storage
- **SES**: Email notifications
- **IAM**: Roles and policies for permissions

## Step 1: Create S3 Bucket

1. Go to AWS Console → S3
2. Click "Create bucket"
3. **Bucket name**: `swing-automation-data-processor`
4. **Region**: `us-east-1` (N. Virginia)
5. **Block Public Access**: Keep all settings checked (default)
6. **Bucket Versioning**: Disable
7. **Default encryption**: Server-side encryption with Amazon S3 managed keys (SSE-S3)
8. Click "Create bucket"

**Validation:**
- Bucket appears in S3 console
- Bucket is in us-east-1 region
- Public access is blocked

## Step 2: Create Secrets Manager Secret

1. Go to AWS Console → Secrets Manager
2. Click "Store a new secret"
3. **Secret type**: Other type of secret
4. **Key/value pairs**: Add the following keys:
   ```json
   {
     "ALPACA_API_KEY": "<YOUR_ALPACA_API_KEY>",
     "ALPACA_SECRET_KEY": "<YOUR_ALPACA_SECRET_KEY>",
     "ALPACA_BASE_URL": "https://paper-api.alpaca.markets"
   }
   ```
5. **Encryption key**: aws/secretsmanager (default)
6. Click "Next"
7. **Secret name**: `swing-alpaca/papter-trading/keys`
8. **Description**: API keys for Alpaca paper trading
9. Click "Next" → "Next" → "Store"

**Validation:**
- Secret appears in Secrets Manager console
- Secret name matches exactly: `swing-alpaca/papter-trading/keys`
- Can retrieve secret value successfully

## Step 3: Setup SES Email

1. Go to AWS Console → Simple Email Service (SES)
2. Click "Verified identities" in left sidebar
3. Click "Create identity"
4. **Identity type**: Email address
5. **Email address**: `mhussain.myindia@outlook.com`
6. Click "Create identity"
7. **Check your email** and click verification link
8. Wait for status to change to "Verified"

**Validation:**
- Email appears in SES console with "Verified" status
- Test email can be sent from SES console

## Step 4: Create IAM Policy

1. Go to AWS Console → IAM → Policies
2. Click "Create policy"
3. Click "JSON" tab
4. Copy and paste the policy from `Policies/swing-lambda-policy.json`
5. Click "Next: Tags" → "Next: Review"
6. **Name**: `swing-lambda-permissions`
7. **Description**: Permissions for swing trading Lambda functions
8. Click "Create policy"

**Validation:**
- Policy appears in IAM → Policies
- Policy JSON matches the provided template
- Policy includes S3, Secrets Manager, and SES permissions

## Step 5: Create IAM Role

1. Go to AWS Console → IAM → Roles
2. Click "Create role"
3. **Trusted entity type**: AWS service
4. **Service**: Lambda
5. Click "Next"
6. **Permissions policies**: Search and select:
   - `swing-lambda-permissions` (custom policy created above)
   - `AWSLambdaBasicExecutionRole` (AWS managed)
7. Click "Next"
8. **Role name**: `swing-automation-lamba-role`
9. **Description**: Execution role for swing trading automation Lambda
10. Click "Create role"

**Validation:**
- Role appears in IAM → Roles
- Role has both required policies attached
- Trust policy allows Lambda service to assume the role

## Step 6: Create Lambda Functions

### Main Trading Bot Lambda

1. Go to AWS Console → Lambda → Functions
2. Click "Create function"
3. **Function name**: `swing-automation-data-processor-lambda`
4. **Runtime**: Python 3.9
5. **Architecture**: x86_64
6. **Execution role**: Use an existing role → `swing-automation-lamba-role`
7. Click "Create function"

**Upload Code:**
1. Navigate to `Lambda` directory in your project
2. Create deployment package:
   ```bash
   powershell Compress-Archive -Path lambda_function.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath lambda_function.zip -Force
   ```
3. In Lambda console, go to "Code" tab
4. Click "Upload from" → ".zip file"
5. Upload `lambda_function.zip`
6. Click "Save"

**Configure Function:**
1. Go to "Configuration" tab → "General configuration"
2. Click "Edit"
3. **Timeout**: 5 minutes
4. **Memory**: 512 MB
5. Click "Save"

**Environment Variables:**
1. Go to "Configuration" tab → "Environment variables"
2. Click "Edit" → "Add environment variable"
3. Add these variables:
   - `BUCKET_NAME`: `swing-automation-data-processor`
   - `EMAIL_RECIPIENT`: `mhussain.myindia@outlook.com`
4. Click "Save"

### Performance Analyzer Lambda

1. Go to AWS Console → Lambda → Functions
2. Click "Create function"
3. **Function name**: `swing-performance-analyzer`
4. **Runtime**: Python 3.9
5. **Architecture**: x86_64
6. **Execution role**: Use an existing role → `swing-automation-lamba-role`
7. Click "Create function"

**Upload Code:**
1. Create deployment package:
   ```bash
   powershell Compress-Archive -Path performance-analyzer.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath swing-performance.zip -Force
   ```
2. Upload `swing-performance.zip` to Lambda function
3. **IMPORTANT**: Change handler to `performance-analyzer.lambda_handler`

**Configure Function:**
1. **Timeout**: 10 minutes
2. **Memory**: 1024 MB
3. **Environment Variables**:
   - `BUCKET_NAME`: `swing-automation-data-processor`
   - `EMAIL_RECIPIENT`: `mhussain.myindia@outlook.com`

**Validation:**
- Both Lambda functions appear in console
- Code is uploaded and handler is correct
- Environment variables are set
- Execution role is attached
- Test functions with sample payloads

## Step 7: Create EventBridge Schedules

### Daily Trading Bot Schedule

1. Go to AWS Console → EventBridge → Schedules
2. Click "Create schedule"
3. **Schedule name**: `swing-bot-daily-trigger`
4. **Description**: Daily execution of swing trading bot
5. **Schedule pattern**: Rate-based schedule
6. **Rate expression**: `cron(45 14 * * MON-FRI *)`
   - This runs at 9:45 AM Toronto time (2:45 PM UTC) on weekdays
7. **Flexible time window**: Off
8. Click "Next"

**Configure Target:**
1. **Target API**: AWS Lambda Invoke
2. **Lambda function**: `swing-automation-data-processor-lambda`
3. **Payload**: 
   ```json
   {
     "symbols": ["AAPL", "NVDA", "MSFT", "AMD", "TSLA"]
   }
   ```
4. **Permissions**: Create new role for this schedule
5. **Role name**: `swing-eventbridge-daily-role`
6. Click "Next" → "Create schedule"

### Weekly Performance Analysis Schedule

1. Go to AWS Console → EventBridge → Schedules
2. Click "Create schedule"
3. **Schedule name**: `swing-performance-weekly`
4. **Description**: Weekly performance analysis
5. **Schedule pattern**: Rate-based schedule
6. **Rate expression**: `cron(0 18 * * FRI *)`
   - This runs at 1:00 PM Toronto time (6:00 PM UTC) on Fridays
7. Click "Next"

**Configure Target:**
1. **Target API**: AWS Lambda Invoke
2. **Lambda function**: `swing-performance-analyzer`
3. **Payload**:
   ```json
   {
     "days_back": 30
   }
   ```
4. **Permissions**: Create new role for this schedule
5. **Role name**: `swing-eventbridge-weekly-role`
6. Click "Next" → "Create schedule"

**Validation:**
- Both schedules appear in EventBridge → Schedules with "Enabled" status
- Cron expressions are correct for Toronto timezone
- Lambda functions are properly targeted
- IAM roles are created for EventBridge

## Step 8: Test the System

### Test Main Lambda
1. Go to AWS Console → Lambda → Functions
2. Click `swing-automation-data-processor-lambda`
3. Click "Test" tab
4. Create test event with payload: `{"symbols": ["AAPL"]}`
5. Click "Test" and check execution results
6. **Validation**: Check CloudWatch logs for successful execution
7. **Validation**: Verify S3 files created in bucket
8. **Validation**: Confirm email notification received

### Test Performance Analyzer
1. Go to AWS Console → Lambda → Functions
2. Click `swing-performance-analyzer`
3. Click "Test" tab
4. Create test event with payload: `{"days_back": 30}`
5. Click "Test" and check execution results
6. **Validation**: Check CloudWatch logs for successful execution
7. **Validation**: Verify performance analysis files in S3
8. **Validation**: Confirm performance summary email received

## Step 9: Monitor and Verify

### Check EventBridge Schedules
1. Go to AWS Console → EventBridge → Schedules
2. Verify schedules `swing-bot-daily-trigger` and `swing-performance-weekly` exist
3. Check schedule status is "Enabled"
4. Click each schedule to verify cron expressions and targets
5. Check "Metrics" tab for execution history

### Check CloudWatch Logs
1. Go to AWS Console → CloudWatch → Log Groups
2. Find log groups:
   - `/aws/lambda/swing-automation-data-processor-lambda`
   - `/aws/lambda/swing-performance-analyzer`
3. Check recent log streams for errors or successful executions
4. Verify no error messages in logs

### Check S3 Data
1. Go to AWS Console → S3
2. Click bucket `swing-automation-data-processor`
3. Verify folder structure: `daily-analysis/`, `symbols/`, `signals/`, `performance/`
4. Check recent files have today's date
5. Download and verify JSON file contents

### Check Email Notifications
1. Check inbox for swing trading emails
2. Verify email format and content
3. Confirm both signal alerts and performance summaries are received
4. Check email timestamps match execution times

## Cleanup Steps (if needed)
1. **Delete Lambda functions**: Go to Lambda → Functions → Delete each function
2. **Delete EventBridge schedules**: Go to EventBridge → Schedules → Delete schedules
3. **Delete IAM role**: Go to IAM → Roles → Delete `swing-automation-lamba-role`
4. **Delete IAM policy**: Go to IAM → Policies → Delete `swing-lambda-permissions`
5. **Delete S3 bucket**: Go to S3 → Empty bucket → Delete bucket
6. **Delete secret**: Go to Secrets Manager → Delete secret

## 🎯 System Status: FULLY OPERATIONAL ✅

All core components are deployed and working:
- ✅ Lambda functions created and tested
- ✅ EventBridge schedules configured for daily/weekly execution
- ✅ S3 bucket storing analysis data
- ✅ Email notifications working via SES
- ✅ Secrets Manager configured with API keys

## 🚀 FUTURE ENHANCEMENTS: Sentiment Analysis Integration

### Overview
Enhance the current RSI/EMA system with sentiment analysis for better signal accuracy and risk management.

### Step A: Setup Sentiment API Sources

### 1. Finnhub API Setup (Primary Source) ✅ COMPLETED
**API Details:**
- **API Key**: <YOUR_FINNHUB_API_KEY>
- **Limits**: 60 calls/minute, unlimited monthly

### 2. NewsAPI Setup (Secondary Source) ✅ COMPLETED
**API Details:**
- **API Key**: <YOUR_NEWSAPI_KEY>
- **Limits**: 1,000 requests/month (free tier)

### 3. Reddit API Setup (Tertiary Source) ✅ COMPLETED
**App Details:**
- **App Name**: SwingBot
- **App Type**: personal use script
- **Username**: <YOUR_REDDIT_USERNAME>
- **Client ID**: <YOUR_REDDIT_CLIENT_ID>
- **Client Secret**: <YOUR_REDDIT_CLIENT_SECRET>
- **Password**: <YOUR_REDDIT_PASSWORD>
- **Limits**: 100 requests/minute

### 4. Update AWS Secrets Manager

⚠️ **SECURITY WARNING**: Use your actual API keys when setting up, but never commit them to public repositories!

**Option A: Manual Console Steps**
1. Go to AWS Console → Secrets Manager
2. Find secret: `swing-alpaca/papter-trading/keys`
3. Click "Retrieve secret value" → "Edit"
4. Add all sentiment API keys to the existing JSON
5. Click "Save"

**Option B: AWS CLI (Recommended)**
1. Open Git Bash terminal
2. Navigate to project directory: `cd Project4-Swing-Automation-System`
3. Run update command:
```bash
aws secretsmanager update-secret \
    --secret-id "swing-alpaca/papter-trading/keys" \
    --secret-string '{
        "ALPACA_API_KEY": "<YOUR_ALPACA_API_KEY>",
        "ALPACA_SECRET_KEY": "<YOUR_ALPACA_SECRET_KEY>",
        "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        "FINNHUB_API_KEY": "<YOUR_FINNHUB_API_KEY>",
        "NEWSAPI_KEY": "<YOUR_NEWSAPI_KEY>",
        "REDDIT_CLIENT_ID": "<YOUR_REDDIT_CLIENT_ID>",
        "REDDIT_CLIENT_SECRET": "<YOUR_REDDIT_CLIENT_SECRET>",
        "REDDIT_USERNAME": "<YOUR_REDDIT_USERNAME>",
        "REDDIT_PASSWORD": "<YOUR_REDDIT_PASSWORD>"
    }'
```
4. Verify update: `aws secretsmanager get-secret-value --secret-id "swing-alpaca/papter-trading/keys"`

🔒 **IMPORTANT**: Always use placeholder values in documentation and replace with actual keys only during deployment!

**Validation:**
- Test each API with curl or browser
- Finnhub: `https://finnhub.io/api/v1/news-sentiment?symbol=AAPL&token=<YOUR_FINNHUB_API_KEY>`
- NewsAPI: `https://newsapi.org/v2/everything?q=AAPL&apiKey=<YOUR_NEWSAPI_KEY>&pageSize=5`

### Step B: Deploy Sentiment-Enhanced Lambda Function

**New Lambda Function Created**: `sentiment-enhanced-lambda.py` (see Lambda folder)

**Manual Deployment Steps:**
1. Navigate to Lambda directory: `cd Lambda`
2. Install additional dependencies: `pip install --no-user pandas numpy -t .`
3. Create deployment package:
   ```bash
   powershell Compress-Archive -Path sentiment-enhanced-lambda.py,requests*,pandas*,numpy*,urllib3*,certifi*,charset_normalizer*,idna*,boto3*,dateutil*,pytz*,six* -DestinationPath sentiment-enhanced-lambda.zip -Force
   ```
4. Go to AWS Console → Lambda
5. Click "Create function"
6. Function name: `swing-sentiment-enhanced-lambda`
7. Runtime: `Python 3.9`
8. Execution role: Use existing role `swing-automation-lamba-role`
9. Click "Create function"
10. Upload zip file in Code section
11. **IMPORTANT**: Change handler to `sentiment-enhanced-lambda.lambda_handler`
12. Set timeout to 10 minutes in Configuration → General
13. Set memory to 1024 MB (sentiment analysis needs more memory)
14. Add environment variables:
    - `BUCKET_NAME`: swing-automation-data-processor
    - `EMAIL_RECIPIENT`: mhussain.myindia@outlook.com
    - `SECRET_NAME`: swing-alpaca/papter-trading/keys

**Test the Enhanced Function:**
1. Create test event: `{"symbols": ["AAPL"]}`
2. Click "Test" and verify:
   - Sentiment data fetched from multiple sources
   - Enhanced signal analysis with confidence scoring
   - Email includes sentiment breakdown
   - S3 files contain sentiment data

**Features of Enhanced Lambda:**
- **Multi-source sentiment**: Finnhub + NewsAPI + Reddit (3 sources)
- **All APIs configured**: Ready for immediate deployment
- **Confidence scoring**: Higher confidence = more sensitive thresholds
- **Rate limiting**: Respects all API limits
- **Enhanced signals**: STRONG/MODERATE/WEAK classifications
- **Detailed logging**: Shows sentiment from each source
- **Error handling**: Graceful degradation if APIs fail
- **Rich email reports**: Includes sentiment breakdown by source

**Update EventBridge Rules (Optional):**
To use the new sentiment-enhanced function:
1. Go to EventBridge → Schedules → `swing-bot-daily-trigger`
2. Click "Edit"
3. Go to "Target" section
4. Change Lambda function to `swing-sentiment-enhanced-lambda`
5. Click "Update schedule"

**Validation:**
- Go to Lambda → `swing-sentiment-enhanced-lambda` → Configuration → Triggers
- Verify EventBridge trigger appears
- Test function with payload: `{"symbols": ["AAPL"]}`
- Check CloudWatch logs for sentiment data fetching

**A/B Testing Approach:**
- Keep original Lambda for comparison
- Run both functions in parallel for 2 weeks
- Compare performance and accuracy
- Switch to sentiment-enhanced version if better results

## 📊 Expected Operational Costs
- **Lambda**: ~$2-3/month (based on daily executions)
- **S3**: ~$0.50/month (for data storage)
- **EventBridge**: ~$0.10/month (for scheduled rules)
- **Secrets Manager**: ~$0.40/month (for API key storage)
- **SES**: Free tier (up to 200 emails/day)
- **Total**: ~$3-4/month

## 🔧 Troubleshooting Common Issues

### Lambda Timeout Errors
- Increase timeout to 5-10 minutes
- Check API response times
- Verify network connectivity

### Email Not Received
- Check SES verified identities
- Verify email address is correct
- Check spam folder
- Review CloudWatch logs for SES errors

### S3 Permission Errors
- Verify IAM role has S3 permissions
- Check bucket name in environment variables
- Ensure bucket exists in correct region

### API Key Errors
- Verify secrets are stored correctly
- Check secret name matches environment variable
- Ensure Lambda role has Secrets Manager permissions
- Test API keys manually

This completes the comprehensive setup guide for the AWS Swing Trading Automation System!