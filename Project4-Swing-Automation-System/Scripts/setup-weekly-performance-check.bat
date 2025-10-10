@echo off
echo 📊 Setting up weekly performance analysis...

echo 📅 Creating EventBridge rule for weekly performance check
aws events put-rule --name swing-performance-weekly --description "Weekly swing trading performance analysis" --schedule-expression "cron(0 18 ? * FRI *)" --state ENABLED

echo 🎯 Adding performance analyzer as target
aws events put-targets --rule swing-performance-weekly --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:206055866143:function:swing-performance-analyzer","Input"="{\"days_back\": 7}"

echo 🔐 Granting EventBridge permission
aws lambda add-permission --function-name swing-performance-analyzer --statement-id allow-eventbridge-performance --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn arn:aws:events:us-east-1:206055866143:rule/swing-performance-weekly

echo ✅ Weekly performance check scheduled for Fridays at 6 PM ET
echo 📊 Manual run: aws lambda invoke --function-name swing-performance-analyzer response.json