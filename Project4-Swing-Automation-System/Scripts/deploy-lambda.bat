@echo off
echo 🚀 Building Lambda deployment package...

cd ..\Lambda

echo 📦 Installing dependencies...
pip install -r requirements.txt -t . --no-user

echo 📁 Creating deployment package...
powershell Compress-Archive -Path *.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath data-processor.zip -Force

echo 🔄 Updating Lambda function...
aws lambda update-function-code --function-name swing-automation-data-processor-lambda --zip-file fileb://data-processor.zip

echo ✅ Lambda function updated successfully!

echo 🧹 Cleaning up dependencies...
rmdir /s /q requests
rmdir /s /q urllib3
rmdir /s /q certifi
rmdir /s /q charset_normalizer
rmdir /s /q idna
del /q requests-*
del /q urllib3-*
del /q certifi-*
del /q charset_normalizer-*
del /q idna-*

echo ✅ Deployment complete!