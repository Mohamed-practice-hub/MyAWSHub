@echo off
echo 🚀 Deploying Performance Analyzer Lambda...

cd ..\Lambda

echo 📦 Installing dependencies for performance analyzer...
pip install requests -t . --no-user

echo 📁 Creating deployment package...
powershell Compress-Archive -Path performance-analyzer.py,requests* -DestinationPath performance-analyzer.zip -Force

echo 🔄 Creating Lambda function...
aws lambda create-function --function-name swing-performance-analyzer --runtime python3.9 --role arn:aws:iam::206055866143:role/swing-automation-lamba-role --handler performance-analyzer.lambda_handler --zip-file fileb://performance-analyzer.zip --timeout 300 --memory-size 256

echo ✅ Performance Analyzer deployed!

echo 🧹 Cleaning up...
del performance-analyzer.zip

echo 📊 Test the analyzer:
echo aws lambda invoke --function-name swing-performance-analyzer --payload "{\"days_back\": 30}" response.json