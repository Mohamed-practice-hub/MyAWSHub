@echo off
echo 🚀 Setting up SES and EventBridge for Swing Trading Bot...

echo 📧 Step 1: Verify email address in SES
aws ses verify-email-identity --email-address mhussain.myindia@outlook.com
echo ✅ Email verification request sent to mhussain.myindia@outlook.com

echo 📅 Step 2: Create EventBridge rule for daily execution
aws events put-rule --name swing-bot-daily-trigger --description "Daily swing trading analysis at 9:45 AM ET" --schedule-expression "cron(45 13 ? * MON-FRI *)" --state ENABLED
echo ✅ EventBridge rule created: swing-bot-daily-trigger

echo 🎯 Step 3: Add Lambda function as target
aws events put-targets --rule swing-bot-daily-trigger --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:206055866143:function:swing-automation-data-processor-lambda"
echo ✅ Lambda target added to EventBridge rule

echo 🔐 Step 4: Grant EventBridge permission to invoke Lambda
aws lambda add-permission --function-name swing-automation-data-processor-lambda --statement-id allow-eventbridge-swing --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn arn:aws:events:us-east-1:206055866143:rule/swing-bot-daily-trigger
echo ✅ EventBridge permission granted

echo 📋 Step 5: Update Lambda IAM role with SES permissions
aws iam put-role-policy --role-name swing-automation-lamba-role --policy-name SESEmailPolicy --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"ses:SendEmail\",\"ses:SendRawEmail\"],\"Resource\":\"*\"}]}"
echo ✅ SES permissions added to Lambda role

echo 🎉 Setup Complete!
echo 📧 Check your email (mhussain.myindia@outlook.com) and click the verification link
echo 📅 Bot will run daily at 9:45 AM ET (Monday-Friday)
echo 🔍 Test manually: aws lambda invoke --function-name swing-automation-data-processor-lambda response.json