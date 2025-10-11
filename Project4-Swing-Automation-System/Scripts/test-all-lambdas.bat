@echo off
echo ========================================
echo AWS Lambda Complete Test Suite
echo ========================================

cd /d "%~dp0.."

echo.
echo [1/3] Testing Main Trading Bot (All 8 Symbols)...
aws lambda invoke --function-name "swing-automation-data-processor-lambda" --payload file://Lambda/test-payloads/all-symbols-payload.json test-results/main-lambda-response.json
if %errorlevel% == 0 (
    echo ✅ Main Lambda: SUCCESS
) else (
    echo ❌ Main Lambda: FAILED
)

echo.
echo [2/3] Testing Performance Analyzer...
aws lambda invoke --function-name "swing-performance-analyzer" --payload file://Lambda/test-payloads/performance-analyzer-payload.json test-results/performance-response.json
if %errorlevel% == 0 (
    echo ✅ Performance Analyzer: SUCCESS
) else (
    echo ❌ Performance Analyzer: FAILED
)

echo.
echo [3/3] Testing Sentiment Enhanced Bot (All 8 Symbols)...
aws lambda invoke --function-name "swing-sentiment-enhanced-lambda" --payload file://Lambda/test-payloads/all-symbols-payload.json test-results/sentiment-response.json
if %errorlevel% == 0 (
    echo ✅ Sentiment Enhanced: SUCCESS
) else (
    echo ❌ Sentiment Enhanced: FAILED
)

echo.
echo ========================================
echo TEST RESULTS SUMMARY
echo ========================================
echo.
echo Main Lambda Response:
type test-results\main-lambda-response.json
echo.
echo.
echo Performance Analyzer Response:
type test-results\performance-response.json
echo.
echo.
echo Sentiment Enhanced Response:
type test-results\sentiment-response.json
echo.
echo ========================================
echo ✅ ALL TESTS COMPLETE!
echo ========================================
echo.
echo Check your Gmail for 3 comprehensive notifications
echo Test results saved in test-results/ folder
echo.
pause