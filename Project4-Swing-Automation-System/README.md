# Project 4: AWS Swing Trading Automation System

## 🎯 Project Overview

This is a fully automated swing trading analysis system built on AWS serverless architecture. The system analyzes 5 tech stocks daily using RSI and EMA technical indicators to generate BUY/SELL/HOLD signals, stores comprehensive data for performance tracking, and sends email alerts for actionable signals.

### 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│  Lambda Function │───▶│   Alpaca API    │
│  (Daily 9:45AM) │    │ (Data Processor) │    │ (Market Data)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SES Email     │◀───│   S3 Storage     │───▶│ Performance     │
│  (Alerts)       │    │ (Analysis Data)  │    │ Analyzer        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 📊 Analyzed Stocks
- **AAPL** (Apple Inc.)
- **NVDA** (NVIDIA Corporation)
- **MSFT** (Microsoft Corporation)
- **AMD** (Advanced Micro Devices)
- **TSLA** (Tesla Inc.)

## 🧠 Trading Strategy

### Technical Indicators Used

#### 1. RSI (Relative Strength Index) - 14 Period
- **Purpose**: Identifies overbought/oversold conditions
- **Range**: 0-100
- **Oversold**: RSI < 30 (potential BUY opportunity)
- **Overbought**: RSI > 70 (potential SELL opportunity)
- **Neutral**: RSI 30-70 (HOLD)

#### 2. EMA (Exponential Moving Average) - 20 Period
- **Purpose**: Identifies trend direction
- **Price > EMA**: Uptrend (bullish)
- **Price < EMA**: Downtrend (bearish)

### Signal Generation Logic

```
BUY Signal:  RSI < 30 AND Price > EMA
SELL Signal: RSI > 70 AND Price < EMA
HOLD Signal: All other conditions
```

### Signal Strength Classification
- **STRONG**: RSI < 25 or RSI > 75
- **MODERATE**: RSI 25-30 or RSI 70-75

## 📁 Data Structure & Storage

### S3 Bucket Organization
```
swing-automation-data-processor/
├── daily-analysis/           # Complete daily analysis
│   └── 2025/01/
│       ├── analysis_20250115_143000.json
│       └── analysis_20250116_143000.json
├── symbols/                  # Individual symbol data
│   ├── AAPL/2025/01/
│   ├── NVDA/2025/01/
│   ├── MSFT/2025/01/
│   ├── AMD/2025/01/
│   └── TSLA/2025/01/
├── signals/                  # BUY/SELL signals only
│   └── 2025/01/
├── performance-reports/      # Weekly performance analysis
└── errors/                   # Error logs
```

## 📊 Understanding the Data

### Daily Analysis File Structure
```json
{
  "symbol": "AAPL",                    // Stock symbol
  "timestamp": "2025-01-15T14:30:00.000Z",  // Analysis time (UTC)
  "analysis_date": "2025-01-15",      // Date of analysis
  "current_price": 185.50,            // Current stock price ($)
  "rsi": 45.2,                        // RSI value (0-100)
  "ema": 182.30,                      // 20-day EMA value ($)
  "signal": "HOLD",                   // Trading signal
  "signal_strength": "MODERATE",      // Signal strength
  "price_vs_ema": 1.75,              // % price above/below EMA
  "historical_prices": [180.1, 181.5, 183.2, 184.0, 185.5],  // Last 10 days
  "price_range_30d": {
    "min": 175.20,                    // 30-day minimum price
    "max": 190.80,                    // 30-day maximum price
    "avg": 182.45                     // 30-day average price
  },
  "technical_indicators": {
    "rsi_oversold": false,            // RSI < 30?
    "rsi_overbought": false,          // RSI > 70?
    "price_above_ema": true,          // Price > EMA?
    "price_below_ema": false          // Price < EMA?
  }
}
```

### How to Read the Signals

#### BUY Signal Example
```json
{
  "symbol": "NVDA",
  "signal": "BUY",
  "current_price": 850.25,
  "rsi": 28.5,                       // ✅ RSI < 30 (oversold)
  "ema": 845.10,                     // ✅ Price > EMA (uptrend)
  "signal_strength": "STRONG"        // RSI < 30 = strong signal
}
```
**Interpretation**: NVDA is oversold (RSI 28.5) but price is above EMA trend line, suggesting a potential bounce-back opportunity.

#### SELL Signal Example
```json
{
  "symbol": "TSLA",
  "signal": "SELL",
  "current_price": 245.80,
  "rsi": 72.3,                       // ✅ RSI > 70 (overbought)
  "ema": 248.50,                     // ✅ Price < EMA (downtrend)
  "signal_strength": "MODERATE"      // RSI 70-75 = moderate signal
}
```
**Interpretation**: TSLA is overbought (RSI 72.3) and price is below EMA trend line, suggesting potential price decline.

#### HOLD Signal Example
```json
{
  "symbol": "AAPL",
  "signal": "HOLD",
  "current_price": 185.50,
  "rsi": 45.2,                       // ❌ RSI neutral (30-70)
  "ema": 182.30,                     // Price > EMA but RSI not extreme
  "signal_strength": "MODERATE"
}
```
**Interpretation**: AAPL is in neutral territory - no clear buy/sell opportunity.

## 📈 Performance Tracking

### Performance Report Structure
```
🎯 SWING TRADING BOT PERFORMANCE REPORT
📊 OVERALL PERFORMANCE:
• Total Signals: 15
• Successful Signals: 9
• Success Rate: 60.0%
• Average Profit/Loss: +2.3%

📈 SIGNAL BREAKDOWN:
• BUY Signals: 8 (Success Rate: 62.5%)
• SELL Signals: 7 (Success Rate: 57.1%)
```

### Success Criteria
- **BUY Signal Success**: Stock price increased after signal
- **SELL Signal Success**: Stock price decreased after signal
- **Profit Calculation**: (Current Price - Signal Price) / Signal Price × 100

## 🔧 System Components

### 1. Main Trading Bot (`lambda_function.py`)
- **Runs**: Daily at 9:45 AM ET (Monday-Friday)
- **Function**: Analyzes stocks, generates signals, sends emails
- **Timeout**: 60 seconds
- **Memory**: 128 MB

### 2. Performance Analyzer (`performance-analyzer.py`)
- **Runs**: Weekly on Fridays at 6:00 PM ET
- **Function**: Analyzes signal accuracy and profitability
- **Timeout**: 300 seconds (5 minutes)
- **Memory**: 256 MB

### 3. Data Sources
- **Market Data**: Alpaca Markets API (paper trading account)
- **Historical Data**: 60 days of daily price data
- **Real-time**: Current market prices for analysis

## 📧 Email Notifications

### Individual Signal Alerts (BUY/SELL only)
```
Subject: 🚨 Swing Signal Alert: NVDA - BUY

Swing Trading Signal Generated:

Symbol: NVDA
Signal: BUY
Price: $850.25
RSI: 28.5
EMA: $845.10
Timestamp: 2025-01-15 14:30:00 UTC

Signal Logic:
- RSI < 30 (Oversold): True
- Price > EMA (Uptrend): True
- RSI > 70 (Overbought): False
- Price < EMA (Downtrend): False
```

### Daily Summary Email
```
Subject: 📊 Daily Swing Analysis Summary - 2 BUY, 1 SELL

Daily Swing Trading Analysis Complete:

Total Symbols Analyzed: 5
BUY Signals: 2
SELL Signals: 1
HOLD Signals: 2

Detailed Results:
NVDA: BUY (Price: $850.25, RSI: 28.5, EMA: $845.10)
TSLA: SELL (Price: $245.80, RSI: 72.3, EMA: $248.50)
AAPL: HOLD (Price: $185.50, RSI: 45.2, EMA: $182.30)
```

## 🎯 How to Use the System

### 1. Monitor Daily Emails
- Check for BUY/SELL signal alerts
- Review daily summary for overall market view
- Strong signals (RSI < 25 or > 75) are higher priority

### 2. Analyze S3 Data
```bash
# Download daily analysis
aws s3 cp s3://swing-automation-data-processor/daily-analysis/2025/01/ . --recursive

# Download specific symbol data
aws s3 cp s3://swing-automation-data-processor/symbols/AAPL/2025/01/ . --recursive

# Download signals only
aws s3 cp s3://swing-automation-data-processor/signals/2025/01/ . --recursive
```

### 3. Check Performance Reports
```bash
# Run manual performance analysis
aws lambda invoke --function-name swing-performance-analyzer response.json

# Download performance reports
aws s3 cp s3://swing-automation-data-processor/performance-reports/ . --recursive
```

## 📊 Key Metrics to Track

### Signal Quality Indicators
1. **RSI Extremes**: Signals with RSI < 25 or > 75 are typically more reliable
2. **EMA Confirmation**: Price should align with trend direction
3. **Signal Strength**: STRONG signals have higher success probability
4. **Price vs EMA %**: Larger deviations often mean stronger signals

### Performance Metrics
1. **Success Rate**: Aim for >60% successful signals
2. **Average Profit**: Target +2% or higher average returns
3. **Risk-Reward Ratio**: Compare average wins vs average losses
4. **Signal Frequency**: Track how often each stock generates signals

## 🚨 Risk Considerations

### System Limitations
- **Paper Trading Only**: Uses simulated trading account data
- **Technical Analysis Only**: No fundamental analysis included
- **Market Hours**: Only analyzes during trading days
- **Lag Time**: 15-minute delay after market open

### Trading Risks
- **False Signals**: Technical indicators can give incorrect signals
- **Market Volatility**: Sudden news can override technical patterns
- **Trend Changes**: EMA is a lagging indicator
- **Overreliance**: Should be combined with other analysis methods

## 🔧 Maintenance & Monitoring

### Daily Checks
- Verify email alerts are received
- Check CloudWatch logs for errors
- Monitor S3 storage usage

### Weekly Reviews
- Review performance reports
- Analyze signal accuracy trends
- Adjust strategy if needed

### Monthly Tasks
- Review AWS costs
- Archive old data if needed
- Update technical parameters if performance declines

## 💰 Cost Breakdown

### Monthly AWS Costs (Estimated)
- **Lambda Executions**: ~$2-3
- **S3 Storage**: ~$1-2
- **SES Emails**: ~$0.10
- **EventBridge**: ~$0.50
- **Secrets Manager**: ~$0.40
- **Total**: ~$4-6 per month

## 🎓 Learning Outcomes

This project demonstrates:
- **Serverless Architecture**: Event-driven, scalable system
- **Financial Data Analysis**: Technical indicator calculations
- **Data Pipeline**: ETL processes with AWS services
- **Performance Monitoring**: Automated backtesting and reporting
- **Cost Optimization**: Efficient resource usage

## 📚 Further Reading

- [RSI Technical Indicator](https://www.investopedia.com/terms/r/rsi.asp)
- [Exponential Moving Average](https://www.investopedia.com/terms/e/ema.asp)
- [Swing Trading Strategies](https://www.investopedia.com/terms/s/swingtrading.asp)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Alpaca Markets API Documentation](https://alpaca.markets/docs/)

---

**⚠️ Disclaimer**: This system is for educational purposes only. Past performance does not guarantee future results. Always conduct your own research before making investment decisions.