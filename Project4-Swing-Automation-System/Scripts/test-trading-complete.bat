@echo off
echo ========================================
echo COMPLETE TRADING SYSTEM TEST
echo ========================================
echo.
echo This will test ALL trading functionality:
echo 1. Forced BUY order test
echo 2. Forced SELL order test  
echo 3. Webhook trading test
echo 4. Portfolio report
echo.
set /p confirm="Continue with trading tests? (y/n): "
if not "%confirm%"=="y" (
    echo Tests cancelled.
    pause
    exit /b
)

cd /d "%~dp0.."

echo.
echo [1/4] Testing FORCED BUY Order...
aws lambda invoke --function-name "swing-trading-test" --payload "{\"test_mode\":\"buy\",\"symbol\":\"AAPL\"}" test-results/forced-buy-test.json
if %errorlevel% == 0 (
    echo ✅ Forced BUY Test: SUCCESS
) else (
    echo ❌ Forced BUY Test: FAILED
)

echo.
echo [2/4] Testing FORCED SELL Order...
aws lambda invoke --function-name "swing-trading-test" --payload "{\"test_mode\":\"sell\",\"symbol\":\"NVDA\"}" test-results/forced-sell-test.json
if %errorlevel% == 0 (
    echo ✅ Forced SELL Test: SUCCESS
) else (
    echo ❌ Forced SELL Test: FAILED
)

echo.
echo [3/4] Testing WEBHOOK Trading...
aws lambda invoke --function-name "swing-webhook-trading" --payload "{\"symbol\":\"MSFT\",\"action\":\"BUY\",\"qty\":2,\"source\":\"test\"}" test-results/webhook-test.json
if %errorlevel% == 0 (
    echo ✅ Webhook Test: SUCCESS
) else (
    echo ❌ Webhook Test: FAILED
)

echo.
echo [4/4] Getting Portfolio Report...
aws lambda invoke --function-name "swing-portfolio-reporter" --payload "{}" test-results/portfolio-after-trades.json
if %errorlevel% == 0 (
    echo ✅ Portfolio Report: SUCCESS
) else (
    echo ❌ Portfolio Report: FAILED
)

echo.
echo ========================================
echo TRADING TEST RESULTS
echo ========================================
echo.
echo Forced BUY Test:
type test-results\forced-buy-test.json
echo.
echo.
echo Forced SELL Test:
type test-results\forced-sell-test.json
echo.
echo.
echo Webhook Test:
type test-results\webhook-test.json
echo.
echo.
echo Portfolio After Trades:
type test-results\portfolio-after-trades.json
echo.
echo ========================================
echo ✅ ALL TRADING TESTS COMPLETE!
echo ========================================
echo.
echo Check Gmail for:
echo 🧪 Forced trading test results
echo 🔗 Webhook execution report
echo 📊 Updated portfolio report
echo.
echo Manual Test Commands:
echo Forced BUY:  aws lambda invoke --function-name "swing-trading-test" --payload "{\"test_mode\":\"buy\",\"symbol\":\"AAPL\"}" response.json
echo Forced SELL: aws lambda invoke --function-name "swing-trading-test" --payload "{\"test_mode\":\"sell\",\"symbol\":\"NVDA\"}" response.json
echo Webhook:     aws lambda invoke --function-name "swing-webhook-trading" --payload "{\"symbol\":\"MSFT\",\"action\":\"BUY\",\"qty\":1}" response.json
echo Portfolio:   aws lambda invoke --function-name "swing-portfolio-reporter" --payload "{}" response.json
echo.
pause