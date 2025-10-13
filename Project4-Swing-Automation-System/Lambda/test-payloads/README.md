# Lambda Test Payloads

This folder contains test payloads and responses for all Lambda functions.

## Test Files

### Main Trading Bot
- **Payload**: `main-trading-bot-payload.json`
- **Response**: `main-trading-bot-response.json`
- **Function**: `swing-automation-data-processor-lambda`

### Performance Analyzer
- **Payload**: `performance-analyzer-payload.json`
- **Response**: `performance-analyzer-response.json`
- **Function**: `swing-performance-analyzer`

### Sentiment Enhanced Bot
- **Payload**: `sentiment-enhanced-payload.json`
- **Response**: `sentiment-enhanced-response.json`
- **Function**: `swing-sentiment-enhanced-lambda`

## Usage

### Manual Testing Commands

```bash
# Test Main Trading Bot
aws lambda invoke --function-name "swing-automation-data-processor-lambda" --payload file://Lambda/test-payloads/main-trading-bot-payload.json response.json

# Test Performance Analyzer
aws lambda invoke --function-name "swing-performance-analyzer" --payload file://Lambda/test-payloads/performance-analyzer-payload.json response.json

# Test Sentiment Enhanced Bot
aws lambda invoke --function-name "swing-sentiment-enhanced-lambda" --payload file://Lambda/test-payloads/sentiment-enhanced-payload.json response.json
```

### Base64 Encoded Payloads (for Git Bash)

```bash
# Main Trading Bot ({"symbols": ["AAPL"]})
aws lambda invoke --function-name "swing-automation-data-processor-lambda" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" response.json

# Performance Analyzer ({"days_back": 30})
aws lambda invoke --function-name "swing-performance-analyzer" --payload "eyJkYXlzX2JhY2siOiAzMH0=" response.json

# Sentiment Enhanced Bot ({"symbols": ["AAPL"]})
aws lambda invoke --function-name "swing-sentiment-enhanced-lambda" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" response.json
```

## Test Results Summary

All Lambda functions executed successfully with comprehensive email notifications:

1. **Main Trading Bot**: Processed AAPL analysis with HOLD signal
2. **Performance Analyzer**: No historical signals found to analyze
3. **Sentiment Enhanced Bot**: Completed enhanced analysis successfully

Check your email (mhussain.myindia@gmail.com) for detailed notification reports from each function.