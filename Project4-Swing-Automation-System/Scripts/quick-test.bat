@echo off
echo ========================================
echo Quick Lambda Test (Single Symbol)
echo ========================================

cd /d "%~dp0.."

echo Testing with AAPL only...
echo.

aws lambda invoke --function-name "swing-automation-data-processor-lambda" --payload file://Lambda/test-payloads/main-trading-bot-payload.json test-results/quick-test.json

echo.
echo Response:
type test-results\quick-test.json
echo.
echo Check Gmail for notification!
pause