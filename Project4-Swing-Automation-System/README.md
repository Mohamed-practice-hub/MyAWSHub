# Project 4: Swing Automation System

## Overview
AWS serverless automation system for data processing, analysis, and notifications.

## Architecture
- **Lambda**: Data processing functions
- **EventBridge**: Scheduled triggers
- **S3**: Data storage and logs
- **SES/SNS**: Notification system
- **CloudWatch**: Monitoring and logging

## Project Structure
```
Project4-Swing-Automation-System/
├── Lambda/                 # Lambda function code
├── Security/              # IAM policies and roles
├── Scripts/               # Deployment scripts
├── Docs/                  # Documentation
└── README.md             # This file
```

## Cost Estimate
- Lambda: ~$5/month
- EventBridge: ~$1/month
- S3: ~$2/month
- SES: ~$1/month
- **Total: ~$9/month**

## Next Steps
1. Set up Lambda functions
2. Configure EventBridge scheduling
3. Create IAM roles and policies
4. Deploy and test system