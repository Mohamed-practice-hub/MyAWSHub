# S3 Data Structure for Swing Trading Analysis

## S3 Bucket Organization

```
swing-automation-data-processor/
├── daily-analysis/           # Complete daily analysis
│   ├── 2025/01/             # Year/Month structure
│   │   ├── analysis_20250115_143000.json
│   │   └── analysis_20250116_143000.json
│   └── 2025/02/
│
├── symbols/                  # Individual symbol data
│   ├── AAPL/
│   │   ├── 2025/01/
│   │   │   ├── AAPL_20250115_143000.json
│   │   │   └── AAPL_20250116_143000.json
│   │   └── 2025/02/
│   ├── NVDA/
│   ├── MSFT/
│   ├── AMD/
│   └── TSLA/
│
├── signals/                  # BUY/SELL signals only
│   ├── 2025/01/
│   │   ├── signals_20250115_143000.json
│   │   └── signals_20250116_143000.json
│   └── 2025/02/
│
└── errors/                   # Error logs
    ├── 2025/01/
    └── 2025/02/
```

## Data Structure Examples

### Daily Analysis File
```json
[
  {
    "symbol": "AAPL",
    "timestamp": "2025-01-15T14:30:00.000Z",
    "analysis_date": "2025-01-15",
    "current_price": 185.50,
    "rsi": 45.2,
    "ema": 182.30,
    "signal": "HOLD",
    "signal_strength": "MODERATE",
    "price_vs_ema": 1.75,
    "historical_prices": [180.1, 181.5, 183.2, 184.0, 185.5],
    "price_range_30d": {
      "min": 175.20,
      "max": 190.80,
      "avg": 182.45
    },
    "technical_indicators": {
      "rsi_oversold": false,
      "rsi_overbought": false,
      "price_above_ema": true,
      "price_below_ema": false
    }
  }
]
```

### Signals File (BUY/SELL only)
```json
[
  {
    "symbol": "NVDA",
    "signal": "BUY",
    "current_price": 850.25,
    "rsi": 28.5,
    "ema": 845.10,
    "signal_strength": "STRONG",
    "timestamp": "2025-01-15T14:30:00.000Z"
  }
]
```

## Future Analysis Capabilities

### Performance Tracking Queries
1. **Signal Accuracy**: Compare BUY signals with future price movements
2. **RSI Effectiveness**: Analyze RSI < 30 vs actual oversold conditions
3. **EMA Trend Analysis**: Track price vs EMA crossovers
4. **Symbol Performance**: Individual stock signal success rates

### Analysis Scripts (Future)
- **Backtest Performance**: Calculate ROI if signals were followed
- **Signal Frequency**: How often each symbol generates signals
- **Market Condition Analysis**: Signal performance in different market conditions
- **Optimization**: Fine-tune RSI/EMA parameters based on historical accuracy

## Data Retention
- **Daily Analysis**: Keep indefinitely for trend analysis
- **Individual Symbols**: Keep 2+ years for backtesting
- **Signals**: Keep permanently for performance tracking
- **Errors**: Keep 1 year for debugging patterns