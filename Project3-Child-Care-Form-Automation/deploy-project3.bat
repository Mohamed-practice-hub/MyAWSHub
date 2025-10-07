@echo off
echo === PROJECT 3: CHILD CARE FORM AUTOMATION DEPLOYMENT ===
echo This will create AWS resources with 'project3' prefix
echo.

REM Set variables
set STACK_NAME=project3-child-care-stack
set PHONE_NUMBER=+14166484282
set REGION=us-east-1

echo Stack Name: %STACK_NAME%
echo Phone Number: %PHONE_NUMBER%
echo Region: %REGION%
echo.

REM Step 1: Deploy CloudFormation Stack
echo Step 1: Deploying CloudFormation stack...
aws cloudformation create-stack --stack-name %STACK_NAME% --template-body file://YAML/child-care-infrastructure.yaml --parameters ParameterKey=ParentPhoneNumber,ParameterValue=%PHONE_NUMBER% --capabilities CAPABILITY_NAMED_IAM --region %REGION%

if %errorlevel% equ 0 (
    echo ✅ Stack creation initiated successfully
) else (
    echo ❌ Stack creation failed
    pause
    exit /b 1
)

REM Step 2: Wait for stack creation
echo.
echo Step 2: Waiting for stack creation to complete...
aws cloudformation wait stack-create-complete --stack-name %STACK_NAME% --region %REGION%

if %errorlevel% equ 0 (
    echo ✅ Stack created successfully
) else (
    echo ❌ Stack creation failed or timed out
    pause
    exit /b 1
)

REM Step 3: Get API Gateway URL
echo.
echo Step 3: Getting API Gateway URL...
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --query "Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue" --output text --region %REGION%') do set API_URL=%%i

echo API Gateway URL: %API_URL%

REM Step 4: Update Lambda function code
echo.
echo Step 4: Updating Lambda function code...
cd Lambda
powershell Compress-Archive -Path * -DestinationPath ../lambda-deployment.zip -Force
cd ..

set FUNCTION_NAME=project3-child-care-process-form
aws lambda update-function-code --function-name %FUNCTION_NAME% --zip-file fileb://lambda-deployment.zip --region %REGION%

if %errorlevel% equ 0 (
    echo ✅ Lambda function updated successfully
    del lambda-deployment.zip
) else (
    echo ❌ Lambda function update failed
)

REM Step 5: Test Lambda function
echo.
echo Step 5: Testing Lambda function...
aws lambda invoke --function-name %FUNCTION_NAME% --payload file://JSON/test-events.json --region %REGION% response.json

if %errorlevel% equ 0 (
    echo ✅ Lambda test completed
    echo Response:
    type response.json
    del response.json
) else (
    echo ❌ Lambda test failed
)

REM Step 6: Display created resources
echo.
echo Step 6: Created AWS Resources with 'project3' prefix:
echo 📋 CloudFormation Stack: %STACK_NAME%
echo 🔧 Lambda Function: project3-child-care-process-form
echo 📡 API Gateway: project3-child-care-api
echo 📱 SNS Topic: project3-child-care-whatsapp
echo 🔐 IAM Role: project3-child-care-lambda-role
echo.
echo 🌐 API Endpoint: %API_URL%
echo 📱 SMS will be sent to: %PHONE_NUMBER%
echo.

REM Step 7: Instructions
echo Step 7: Next Steps:
echo 1. Update HTML/child-care-form.html with API URL:
echo    Replace: const API_ENDPOINT = 'https://your-api-gateway-url...'
echo    With:    const API_ENDPOINT = '%API_URL%'
echo.
echo 2. Open HTML/child-care-form.html in browser to test
echo.

echo === DEPLOYMENT COMPLETED ===
echo All resources created with 'project3' prefix for easy identification
pause