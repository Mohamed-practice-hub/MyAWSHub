# AWS Swing Trading Automation System

## 🎯 Overview
Fully automated swing trading system using RSI/EMA technical indicators with sentiment analysis enhancement, running on AWS serverless architecture. The system analyzes 8 symbols daily and provides comprehensive email notifications for all activities.

## 📊 Current Portfolio
**8 Symbols Analyzed Daily:**
- **Individual Stocks**: AAPL, NVDA, MSFT, AMD, TSLA
- **ETFs**: ARKK (Innovation), BOTZ (Robotics), QQQ (NASDAQ-100)

## 🏗️ System Architecture

### Core Components
- **3 Lambda Functions**: Main trading bot, Performance analyzer, Sentiment-enhanced bot
- **EventBridge Schedules**: Daily trading analysis + Weekly performance reports
- **S3 Storage**: Organized data structure for all trading data
- **SES Email**: Comprehensive notifications for all function executions
- **Secrets Manager**: Secure API key storage (Alpaca + Sentiment APIs)
- **IAM Roles/Policies**: Proper permissions for all services

### Data Flow
```
EventBridge → Lambda Functions → Alpaca API → Technical Analysis → Sentiment Analysis → S3 Storage → Email Notifications
```

## 🤖 Lambda Functions

### 1. Main Trading Bot (`swing-automation-data-processor-lambda`)
**Purpose**: Core technical analysis using RSI and EMA indicators
**Schedule**: Daily at 9:45 AM Toronto time (weekdays)
**Features**:
- RSI + EMA technical analysis
- BUY/SELL/HOLD signal generation
- S3 data storage
- Comprehensive email notifications

### 2. Sentiment-Enhanced Bot (`swing-sentiment-enhanced-lambda`) ✅ ACTIVE
**Purpose**: Enhanced analysis with multi-source sentiment data
**Schedule**: Daily at 9:45 AM Toronto time (weekdays) - Currently Active
**Features**:
- Multi-source sentiment analysis (Finnhub + NewsAPI)
- Adaptive RSI thresholds based on sentiment
- Enhanced signal confidence scoring
- Sentiment-influenced decision making

### 3. Performance Analyzer (`swing-performance-analyzer`)
**Purpose**: Historical signal accuracy and profit/loss analysis
**Schedule**: Weekly on Fridays at 1:00 PM Toronto time
**Features**:
- Historical signal performance tracking
- Success rate calculations
- Profit/loss analysis
- Top/worst performer identification

### 4. Trading Executor (`swing-trading-executor`) 🚨 LIVE TRADING
**Purpose**: Executes actual BUY/SELL orders via Alpaca paper trading
**Features**:
- Real order execution (paper trading account)
- Market order placement
- Order tracking and status monitoring
- Comprehensive trade execution emails

### 5. Portfolio Reporter (`swing-portfolio-reporter`) 📊 P&L TRACKING
**Purpose**: Real-time portfolio monitoring and profit/loss reporting
**Features**:
- Current positions and market values
- Unrealized profit/loss calculations
- Recent trading activity
- Account summary and buying power

### 6. Webhook Trading (`swing-webhook-trading`) 🔗 REAL-TIME
**Purpose**: Processes external trading signals via webhooks
**Features**:
- Finnhub webhook integration
- Real-time signal processing
- Instant trade execution
- External system integration
**Webhook URL**: `https://8ekleumcyf.execute-api.us-east-1.amazonaws.com/prod/webhook`

### 7. Trading Test (`swing-trading-test`) 🧪 TESTING
**Purpose**: Forced trading tests to validate BUY/SELL functionality
**Features**:
- Forced BUY/SELL order placement
- Trading system validation
- Test result reporting

## 📧 Email Notification System

### Comprehensive Notifications
**All 3 functions send detailed email reports regardless of results:**

#### Daily Trading Analysis Emails
- **Subject**: Function type and date
- **Content**: Complete analysis breakdown
- **Frequency**: Every weekday at 9:45 AM Toronto time
- **Includes**: All symbols, signals, technical data, sentiment (if applicable)

#### Weekly Performance Emails
- **Subject**: Performance Analysis Report
- **Content**: Historical signal accuracy and P&L
- **Frequency**: Every Friday at 1:00 PM Toronto time
- **Includes**: Success rates, top performers, detailed metrics

#### Error Notifications
- **Subject**: Error Report with function name
- **Content**: Detailed error information and troubleshooting steps
- **Frequency**: When errors occur
- **Includes**: Error details, attempted symbols, next steps

## 🔧 Trading Logic

### Signal Generation
```
BUY Signal:  RSI < 30 AND Price > EMA
SELL Signal: RSI > 70 AND Price < EMA
HOLD Signal: All other conditions
```

### Sentiment Enhancement (Active Function)
```
Adjusted BUY Threshold:  RSI < (30 + sentiment_score * 5 * confidence)
Adjusted SELL Threshold: RSI > (70 - sentiment_score * 5 * confidence)
```

### Trade Execution
- **Paper Trading**: All trades executed in Alpaca paper account
- **Market Orders**: Immediate execution at current market price
- **Order Tracking**: All orders logged with IDs and status
- **Risk Management**: 1 share per trade for testing

### Webhook Integration
- **Real-time Signals**: External systems can trigger trades
- **Finnhub Integration**: Price alerts and technical indicators
- **Authentication**: Secure webhook with Finnhub secret validation
- **Instant Execution**: Sub-second trade execution from external signals

## 📁 S3 Data Structure
```
swing-automation-data-processor/
├── daily-analysis/           # Daily complete analysis
├── symbols/                  # Individual symbol data
│   ├── AAPL/
│   ├── NVDA/
│   ├── MSFT/
│   ├── AMD/
│   ├── TSLA/
│   ├── ARKK/
│   ├── BOTZ/
│   └── QQQ/
├── signals/                  # BUY/SELL signals only
├── performance-reports/      # Weekly performance analysis
├── trading-results/          # Actual trade executions
├── webhook-trades/           # Webhook-triggered trades
└── errors/                   # Error logs
```

## 🚀 Manual Triggers

### Analysis Functions
```bash
# Sentiment-enhanced analysis (currently active)
aws lambda invoke --function-name "swing-sentiment-enhanced-lambda" --payload "eyJzeW1ib2xzIjpbIkFBUEwiLCJOVkRBIiwiTVNGVCIsIkFNRCIsIlRTTEEiLCJBUktLIiwiQk9UWiIsIlFRUSJdfQ==" response.json

# Performance analysis
aws lambda invoke --function-name "swing-performance-analyzer" --payload "eyJkYXlzX2JhY2siOiAzMH0=" response.json
```

### Trading Functions
```bash
# Execute trades based on current signals
aws lambda invoke --function-name "swing-trading-executor" --payload "eyJzeW1ib2xzIjpbIkFBUEwiXX0=" response.json

# Get portfolio report with P&L
aws lambda invoke --function-name "swing-portfolio-reporter" --payload "{}" response.json

# Test forced BUY order
aws lambda invoke --function-name "swing-trading-test" --payload "eyJ0ZXN0X21vZGUiOiJidXkiLCJzeW1ib2wiOiJBQVBMIn0=" response.json

# Test webhook trading
aws lambda invoke --function-name "swing-webhook-trading" --payload "eyJzeW1ib2wiOiJNU0ZUIiwiYWN0aW9uIjoiQlVZIiwicXR5IjoxfQ==" response.json
```

### Webhook Testing
```bash
# Test webhook via HTTP
curl -X POST "https://8ekleumcyf.execute-api.us-east-1.amazonaws.com/prod/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Finnhub-Secret: d3l5chpr01qq28em0po0" \
  -d '{"symbol":"AAPL","action":"BUY","qty":1}'
```

### System Status
```bash
# Check all functions
aws lambda list-functions --query "Functions[?contains(FunctionName, 'swing')]"

# Check recent webhook activity
aws s3 ls s3://swing-automation-data-processor/webhook-trades/2025/10/ --recursive
```

## 🔑 API Keys & Configuration

### Required APIs
- **Alpaca Markets**: Stock data (paper trading account)
- **Finnhub**: Sentiment analysis (primary source)
- **NewsAPI**: News sentiment analysis (secondary source)
- **Reddit**: Social sentiment (tertiary source - placeholder)

### Secrets Manager
**Secret Name**: `swing-alpaca/papter-trading/keys`
**Contains**: All API keys securely stored
**Access**: Lambda functions retrieve keys automatically

## ⏰ Scheduling

### Daily Trading Analysis
- **Time**: 9:45 AM Toronto time (weekdays only)
- **Function**: `swing-sentiment-enhanced-lambda` (currently active)
- **EventBridge**: `swing-bot-daily-trigger`

### Weekly Performance Analysis
- **Time**: 1:00 PM Toronto time (Fridays only)
- **Function**: `swing-performance-analyzer`
- **EventBridge**: `swing-performance-weekly`

## 💰 Operational Costs
- **Lambda**: ~$2-3/month (daily + weekly executions)
- **S3**: ~$0.50/month (data storage)
- **EventBridge**: ~$0.10/month (scheduled triggers)
- **Secrets Manager**: ~$0.40/month (API key storage)
- **SES**: Free tier (up to 200 emails/day)
- **Total**: ~$3-4/month

## 🔧 Automated Deployment

### Deployment Scripts
Located in `Scripts/` folder:
- `deploy-lambda.sh` - Main deployment script with change detection
- `deploy-lambda.bat` - Windows wrapper
- `watch-and-deploy.sh` - File watcher for continuous deployment

### Usage
```bash
# Deploy changed functions
cd Scripts && ./deploy-lambda.sh

# Force deploy all functions
cd Scripts && ./deploy-lambda.sh --force

# Windows users
cd Scripts && deploy-lambda.bat
```

## 📈 Performance Tracking

### Metrics Tracked
- **Signal Accuracy**: Success rate of BUY/SELL signals
- **Profit/Loss**: Theoretical P&L from signals
- **Signal Distribution**: BUY vs SELL signal frequency
- **Symbol Performance**: Best/worst performing symbols
- **Time Analysis**: Signal duration and timing

### Reports Generated
- **Weekly Performance Reports**: Comprehensive analysis
- **Daily Signal Logs**: All trading decisions
- **Error Tracking**: System health monitoring
- **Historical Trends**: Long-term performance patterns

## 🛠️ Troubleshooting

### Common Issues
1. **No Email Received**: Check spam folder, verify SES identity
2. **API Errors**: Check Secrets Manager keys, API limits
3. **Lambda Timeouts**: Increase timeout, check API response times
4. **S3 Permissions**: Verify IAM role permissions

### Monitoring
- **CloudWatch Logs**: Detailed execution logs for all functions
- **S3 Data**: Verify daily data creation
- **Email Notifications**: Comprehensive status reports
- **EventBridge Metrics**: Schedule execution history

## 🎯 System Status: 100% OPERATIONAL ✅

### Current Configuration
- ✅ **7 Lambda Functions**: All deployed and tested
- ✅ **Live Trading**: Paper trading account with real order execution
- ✅ **Webhook Integration**: Finnhub real-time signals operational
- ✅ **Portfolio Tracking**: Real-time P&L monitoring
- ✅ **Sentiment Analysis**: Active for daily trading
- ✅ **8 Symbol Portfolio**: Stocks + ETFs analyzed daily
- ✅ **Comprehensive Emails**: All functions send detailed reports
- ✅ **Automated Scheduling**: Daily + weekly execution
- ✅ **Performance Tracking**: Historical analysis active
- ✅ **Cost Optimized**: Under $5/month operation

### Trading Capabilities
- 🚨 **Real Order Execution**: Proven with successful BUY/SELL orders
- 📊 **Portfolio Management**: $100,000 paper trading account
- 🔗 **Webhook Trading**: External signals trigger instant trades
- 📧 **Trade Notifications**: Detailed execution reports via email
- 🧪 **Testing Framework**: Comprehensive trading validation tools

### Webhook URL
**Finnhub Integration**: `https://8ekleumcyf.execute-api.us-east-1.amazonaws.com/prod/webhook`

### Next Steps
**System is fully operational** - Configure Finnhub alerts for real-time tradingal and automated!

The system will:
1. **Analyze 8 symbols daily** with sentiment-enhanced analysis
2. **Send comprehensive email reports** for all executions
3. **Store all data** in organized S3 structure
4. **Track performance** with weekly analysis reports
5. **Operate autonomously** with minimal maintenance required

---

## 📞 Support & Maintenance

### Regular Monitoring
- **Daily**: Check email notifications for system health
- **Weekly**: Review performance analysis reports
- **Monthly**: Monitor AWS costs and API usage limits

### Updates & Modifications
- Use deployment scripts for code updates
- Modify symbol list via EventBridge payload
- Adjust schedules via EventBridge console
- Update API keys via Secrets Manager

**Your AWS Swing Trading Automation System is production-ready and fully operational!** 🚀📈