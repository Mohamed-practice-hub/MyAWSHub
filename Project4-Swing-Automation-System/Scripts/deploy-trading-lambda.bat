@echo off
echo ========================================
echo Deploy Trading Lambda (WITH REAL TRADES)
echo ========================================
echo.
echo ⚠️  WARNING: This Lambda will execute REAL trades!
echo ⚠️  Make sure you want to enable automated trading!
echo.
set /p confirm="Type 'YES' to deploy trading Lambda: "
if not "%confirm%"=="YES" (
    echo Deployment cancelled.
    pause
    exit /b
)

cd /d "%~dp0.."

echo.
echo [1/4] Creating trading deployment folder...
if exist deployment\trading-lambda rmdir /s /q deployment\trading-lambda
mkdir deployment\trading-lambda

echo.
echo [2/4] Copying trading Lambda and installing dependencies...
copy Lambda\trading-lambda.py deployment\trading-lambda\
cd deployment\trading-lambda
pip install --no-user requests -t . >nul 2>&1

echo.
echo [3/4] Creating deployment package...
powershell -Command "Compress-Archive -Path * -DestinationPath trading-lambda.zip -Force" >nul

echo.
echo [4/4] Creating new Lambda function...
aws lambda create-function ^
    --function-name "swing-trading-executor" ^
    --runtime python3.13 ^
    --role "arn:aws:iam::206055866143:role/swing-automation-lamba-role" ^
    --handler "trading-lambda.lambda_handler" ^
    --zip-file fileb://trading-lambda.zip ^
    --timeout 300 ^
    --memory-size 256 ^
    --environment Variables="{BUCKET_NAME=swing-automation-data-processor}"

echo.
echo ========================================
echo ✅ TRADING LAMBDA DEPLOYED!
echo ========================================
echo.
echo Function Name: swing-trading-executor
echo ⚠️  This function will execute REAL trades!
echo.
echo Test with: aws lambda invoke --function-name "swing-trading-executor" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" response.json
echo.
pause