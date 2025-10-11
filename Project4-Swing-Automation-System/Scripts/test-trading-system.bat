@echo off
echo ========================================
echo Complete Trading System Test
echo ========================================

cd /d "%~dp0.."

echo.
echo [1/3] Testing Trading Executor (AAPL)...
aws lambda invoke --function-name "swing-trading-executor" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" test-results/trading-test.json
if %errorlevel% == 0 (
    echo ✅ Trading Executor: SUCCESS
) else (
    echo ❌ Trading Executor: FAILED
)

echo.
echo [2/3] Testing Portfolio Reporter...
aws lambda invoke --function-name "swing-portfolio-reporter" --payload "{}" test-results/portfolio-report.json
if %errorlevel% == 0 (
    echo ✅ Portfolio Reporter: SUCCESS
) else (
    echo ❌ Portfolio Reporter: FAILED
)

echo.
echo [3/3] Testing Analysis Lambda (All Symbols)...
aws lambda invoke --function-name "swing-automation-data-processor-lambda" --payload "eyJzeW1ib2xzIjpbIkFBUEwiLCJOVkRBIiwiTVNGVCIsIkFNRCIsIlRTTEEiLCJBUktLIiwiQk9UWiIsIlFRUSJdfQ==" test-results/analysis-test.json
if %errorlevel% == 0 (
    echo ✅ Analysis Lambda: SUCCESS
) else (
    echo ❌ Analysis Lambda: FAILED
)

echo.
echo ========================================
echo TEST RESULTS
echo ========================================
echo.
echo Trading Test Result:
type test-results\trading-test.json
echo.
echo.
echo Portfolio Report Result:
type test-results\portfolio-report.json
echo.
echo ========================================
echo ✅ TRADING SYSTEM TESTS COMPLETE!
echo ========================================
echo.
echo Check Gmail for:
echo 🚨 Trading execution report
echo 📊 Portfolio report with P&L
echo 📉 Analysis report
echo.
echo Manual Commands:
echo Trading: aws lambda invoke --function-name "swing-trading-executor" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" response.json
echo Portfolio: aws lambda invoke --function-name "swing-portfolio-reporter" --payload "{}" response.json
echo.
pause