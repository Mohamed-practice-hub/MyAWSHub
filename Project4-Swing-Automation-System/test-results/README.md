# Lambda Test Results

This directory contains test results from Lambda function executions.

## Latest Test Results

### All 8 Symbols Test (2025-10-11)

**Main Trading Bot:**
- ✅ Processed 8 symbols successfully
- Symbols: AAPL, NVDA, MSFT, AMD, TSLA, ARKK, BOTZ, QQQ
- All signals: HOLD (no BUY/SELL signals generated)
- Notable: TSLA, ARKK, BOTZ, QQQ all have high RSI (>75) indicating overbought conditions

**Performance Analyzer:**
- ✅ Executed successfully
- Result: No historical signals found (expected for new system)

**Sentiment Enhanced Bot:**
- ✅ Processed 8 symbols successfully
- No trading signals generated
- Enhanced analysis with sentiment data

## Test Payloads Used

### Base64 Encoded Payloads
- **All 8 Symbols**: `eyJzeW1ib2xzIjpbIkFBUEwiLCJOVkRBIiwiTVNGVCIsIkFNRCIsIlRTTEEiLCJBUktLIiwiQk9UWiIsIlFRUSJdfQ==`
- **Performance Test**: `eyJkYXlzX2JhY2siOiAzMH0=`
- **Single AAPL**: `eyJzeW1ib2xzIjpbIkFBUEwiXX0=`

### JSON Payloads
- **All Symbols**: `{"symbols": ["AAPL", "NVDA", "MSFT", "AMD", "TSLA", "ARKK", "BOTZ", "QQQ"]}`
- **Performance**: `{"days_back": 30}`
- **Single Symbol**: `{"symbols": ["AAPL"]}`

## Test Scripts Available

- `Scripts\test-all-lambdas-fixed.bat` - Complete test suite
- `Scripts\quick-test.bat` - Single symbol test
- Manual commands with base64 payloads

## Email Notifications

All tests trigger Gmail notifications to `mhussain.myindia@gmail.com` with comprehensive analysis reports.