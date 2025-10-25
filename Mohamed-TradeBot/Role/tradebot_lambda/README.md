# tradebot_lambda IAM Role Setup

This folder contains scripts and documentation for creating and managing the IAM role for all TradeBot Lambda functions.

## Scripts
- `create-tradebot-lambda-role.sh`: Bash script to create the `tradebot-lambda-role` and attach all required AWS managed policies.

## Usage

```bash
cd "C:\workarea\AWS Practice Projects\Mohamed-aws-portfolio-projects\Mohamed-TradeBot\Role\tradebot_lambda"
bash create-tradebot-lambda-role.sh
```

## Required Policies
- AWSLambdaBasicExecutionRole
- AmazonDynamoDBFullAccess
- AmazonSESFullAccess
- AmazonS3FullAccess
- SecretsManagerReadWrite

---

**Store all future role-related scripts and documentation for TradeBot Lambdas in this folder.**
