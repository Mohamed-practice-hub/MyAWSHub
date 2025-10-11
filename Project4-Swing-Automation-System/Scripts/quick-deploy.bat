@echo off
REM Quick deployment script that runs directly from current directory
REM No directory changes needed

echo 🚀 Quick Lambda Deployment
echo ========================

REM Set paths relative to current location
set LAMBDA_DIR=..\Lambda
set MAIN_FUNCTION=swing-automation-data-processor-lambda
set PERFORMANCE_FUNCTION=swing-performance-analyzer

echo Checking Lambda functions...

REM Deploy main function
echo.
echo 📦 Deploying Main Trading Bot...
cd /d "%LAMBDA_DIR%"
powershell -Command "Compress-Archive -Path lambda_function.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath lambda_function.zip -Force"
aws lambda update-function-code --function-name %MAIN_FUNCTION% --zip-file fileb://lambda_function.zip
del lambda_function.zip
cd /d "%~dp0"
echo ✅ Main function deployed

REM Deploy performance function
echo.
echo 📊 Deploying Performance Analyzer...
cd /d "%LAMBDA_DIR%"
powershell -Command "Compress-Archive -Path performance-analyzer.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath swing-performance.zip -Force"
aws lambda update-function-code --function-name %PERFORMANCE_FUNCTION% --zip-file fileb://swing-performance.zip
del swing-performance.zip
cd /d "%~dp0"
echo ✅ Performance analyzer deployed

echo.
echo 🎉 Deployment complete!
pause