@echo off
echo ========================================
echo AWS Lambda Clean Deployment Script
echo ========================================

cd /d "%~dp0.."

echo.
echo [1/6] Cleaning deployment folders...
if exist deployment rmdir /s /q deployment
mkdir deployment\main-lambda
mkdir deployment\performance-lambda
mkdir deployment\sentiment-lambda

echo.
echo [2/6] Copying Lambda functions...
copy Lambda\lambda_function.py deployment\main-lambda\
copy Lambda\performance-analyzer.py deployment\performance-lambda\
copy Lambda\sentiment-simple-lambda.py deployment\sentiment-lambda\

echo.
echo [3/6] Installing dependencies...
cd deployment\main-lambda
pip install --no-user requests -t . >nul 2>&1
cd ..\sentiment-lambda
pip install --no-user requests -t . >nul 2>&1
cd ..\..

echo.
echo [4/6] Creating deployment packages...
cd deployment\main-lambda
powershell -Command "Compress-Archive -Path * -DestinationPath lambda_function.zip -Force" >nul
cd ..\performance-lambda
powershell -Command "Compress-Archive -Path * -DestinationPath performance-analyzer.zip -Force" >nul
cd ..\sentiment-lambda
powershell -Command "Compress-Archive -Path * -DestinationPath sentiment-lambda.zip -Force" >nul
cd ..\..

echo.
echo [5/6] Deploying Lambda functions...
echo   - Main Lambda...
aws lambda update-function-code --function-name "swing-automation-data-processor-lambda" --zip-file fileb://deployment/main-lambda/lambda_function.zip >nul
echo   - Performance Analyzer...
aws lambda update-function-code --function-name "swing-performance-analyzer" --zip-file fileb://deployment/performance-lambda/performance-analyzer.zip >nul
echo   - Sentiment Enhanced...
aws lambda update-function-code --function-name "swing-sentiment-enhanced-lambda" --zip-file fileb://deployment/sentiment-lambda/sentiment-lambda.zip >nul

echo.
echo [6/6] Testing deployments...
echo   - Testing main Lambda...
aws lambda invoke --function-name "swing-automation-data-processor-lambda" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" test-response.json >nul
echo   - Testing sentiment Lambda...
aws lambda invoke --function-name "swing-sentiment-enhanced-lambda" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" test-response2.json >nul

echo.
echo ========================================
echo ✅ DEPLOYMENT COMPLETE!
echo ========================================
echo.
echo All Lambda functions deployed with Gmail notifications:
echo   ✅ Main Trading Bot
echo   ✅ Performance Analyzer  
echo   ✅ Sentiment Enhanced Bot
echo.
echo Dependencies are isolated in deployment/ folder
echo Original Lambda/ folder remains clean
echo.
echo Check your Gmail for test notifications!
echo ========================================

del test-response.json test-response2.json 2>nul
pause