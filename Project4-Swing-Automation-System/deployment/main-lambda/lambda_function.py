import boto3
import json
import requests
import os
from datetime import datetime, timedelta

def get_alpaca_keys():
    """Retrieve Alpaca API keys from AWS Secrets Manager"""
    print("🔑 Starting to retrieve Alpaca API keys from Secrets Manager...")
    client = boto3.client('secretsmanager')
    secret_name = "swing-alpaca/papter-trading/keys"
    print(f"📋 Secret name: {secret_name}")
    try:
        print("🔍 Calling get_secret_value...")
        response = client.get_secret_value(SecretId=secret_name)
        print("✅ Successfully retrieved secret from AWS")
        secret = json.loads(response['SecretString'])
        print(f"🔧 Secret keys found: {list(secret.keys())}")
        return secret['ALPACA_API_KEY'], secret['ALPACA_SECRET_KEY']
    except Exception as e:
        print(f"❌ Error retrieving secrets: {e}")
        raise

# Initialize outside handler for better performance
print("🚀 Starting Lambda initialization...")
try:
    API_KEY, SECRET_KEY = get_alpaca_keys()
    print(f"✅ API keys retrieved successfully (API_KEY length: {len(API_KEY) if API_KEY else 0})")
    BASE_URL = "https://data.alpaca.markets"
    print(f"🌐 Base URL set: {BASE_URL}")
    HEADERS = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY
    }
    print("📝 Headers configured for Alpaca API")
    s3_client = boto3.client('s3')
    ses_client = boto3.client('ses')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')
    print(f"🪣 S3 bucket configured: {S3_BUCKET}")
    print("📧 SES client initialized")
    print("✅ Initialization completed successfully")
except Exception as e:
    print(f"❌ Initialization error: {e}")
    API_KEY = SECRET_KEY = None

def get_bars(symbol, timeframe="1Day", limit=30):
    """Fetch historical price data from Alpaca"""
    print(f"📊 Fetching {limit} {timeframe} bars for {symbol}...")
    
    # Calculate dynamic start date (60 days back to ensure enough data)
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    print(f"📅 Dynamic start date: {start_date}")
    
    url = f"{BASE_URL}/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": timeframe,
        "limit": limit,
        "start": start_date
    }
    print(f"🔗 API URL: {url}")
    print(f"📋 Parameters: {params}")
    try:
        print(f"🌐 Making API request to Alpaca...")
        response = requests.get(url, headers=HEADERS, params=params)
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API Error Response: {response.text}")
        
        response.raise_for_status()
        data = response.json()
        print(f"🔍 Full API response: {json.dumps(data, indent=2)[:500]}...")
        
        bars = data.get('bars', [])
        print(f"📈 Received {len(bars)} bars for {symbol}")
        
        if not bars:
            print(f"⚠️ No bars returned for {symbol}")
            return []
            
        prices = [float(bar['c']) for bar in bars]
        print(f"💰 Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        return prices
    except Exception as e:
        print(f"❌ Error fetching data for {symbol}: {e}")
        import traceback
        print(f"📋 Full error traceback: {traceback.format_exc()}")
        return []

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    print(f"📊 Calculating RSI with {len(prices)} prices, period={period}")
    if len(prices) < period + 1:
        print(f"⚠️ Not enough data for RSI calculation, returning neutral (50)")
        return 50  # Default neutral RSI
    
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    print(f"📈 Avg Gain: {avg_gain:.4f}, Avg Loss: {avg_loss:.4f}")
    
    if avg_loss == 0:
        print("📈 No losses detected, RSI = 100")
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    print(f"📊 Calculated RSI: {rsi:.2f}")
    return rsi

def calculate_ema(prices, period=20):
    """Calculate Exponential Moving Average"""
    print(f"📊 Calculating EMA with {len(prices)} prices, period={period}")
    if len(prices) < period:
        simple_avg = sum(prices) / len(prices)
        print(f"⚠️ Not enough data for full EMA, using simple average: {simple_avg:.2f}")
        return simple_avg  # Simple average if not enough data
    
    ema = prices[0]
    multiplier = 2 / (period + 1)
    print(f"🔢 EMA multiplier: {multiplier:.4f}")
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    print(f"📊 Calculated EMA: {ema:.2f}")
    return ema

def send_comprehensive_daily_email(results):
    """Send comprehensive daily analysis email"""
    try:
        buy_signals = [r for r in results if r['signal'] == 'BUY']
        sell_signals = [r for r in results if r['signal'] == 'SELL']
        hold_signals = [r for r in results if r['signal'] == 'HOLD']
        
        subject = f"📉 Main Trading Analysis - {datetime.utcnow().strftime('%Y-%m-%d')}"
        
        body = f"""
MAIN SWING TRADING ANALYSIS
{'='*60}
Function: MAIN-TRADING-BOT
Date: {datetime.utcnow().strftime('%Y-%m-%d')}
Time: {datetime.utcnow().strftime('%H:%M:%S')} UTC
Status: COMPLETED SUCCESSFULLY

SYMBOLS ANALYZED: {len(results)}
SIGNALS GENERATED: {len(buy_signals) + len(sell_signals)}

SIGNAL BREAKDOWN:
• BUY Signals: {len(buy_signals)}
• SELL Signals: {len(sell_signals)}
• HOLD Signals: {len(hold_signals)}

DETAILED ANALYSIS:
{'-'*40}
"""
        
        for result in results:
            signal_emoji = "🟢" if result['signal'] == 'BUY' else "🔴" if result['signal'] == 'SELL' else "🟡"
            body += f"""
{signal_emoji} {result['symbol']}: {result['signal']} ({result.get('signal_strength', 'MODERATE')})
  Price: ${result['current_price']:.2f} | RSI: {result['rsi']} | EMA: ${result['ema']:.2f}
  Technical: RSI {'oversold' if result['rsi'] < 30 else 'overbought' if result['rsi'] > 70 else 'neutral'}, Price {'above' if result['current_price'] > result['ema'] else 'below'} EMA
"""
        
        body += f"""

{'='*60}
AWS SWING TRADING AUTOMATION SYSTEM
Function: MAIN-TRADING-BOT
Execution Time: {datetime.utcnow().isoformat()}
Next Scheduled Run: Check EventBridge schedules
{'='*60}
"""
        
        ses_client.send_email(
            Source='mhussain.myindia@gmail.com',
            Destination={'ToAddresses': ['mhussain.myindia@gmail.com']},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        print(f"Comprehensive daily analysis email sent successfully")
        
    except Exception as e:
        print(f"Error sending comprehensive daily email: {e}")

def send_comprehensive_error_email(symbols, error_log):
    """Send comprehensive error notification email"""
    try:
        subject = f"⚠️ Main Trading Analysis - Error Report - {datetime.utcnow().strftime('%Y-%m-%d')}"
        
        body = f"""
MAIN SWING TRADING ANALYSIS - ERROR REPORT
{'='*60}
Function: MAIN-TRADING-BOT
Date: {datetime.utcnow().strftime('%Y-%m-%d')}
Time: {datetime.utcnow().strftime('%H:%M:%S')} UTC
Status: COMPLETED WITH ERRORS

ERROR DETAILS:
{'-'*40}
Error: {error_log['error']}
Symbols Attempted: {', '.join(symbols)}
Timestamp: {error_log['timestamp']}

TROUBLESHOOTING:
• Check Alpaca API connectivity
• Verify API keys in Secrets Manager
• Review CloudWatch logs for detailed errors
• Market may be closed or data unavailable

The system will retry on the next scheduled run.

{'='*60}
AWS SWING TRADING AUTOMATION SYSTEM
Function: MAIN-TRADING-BOT
Execution Time: {datetime.utcnow().isoformat()}
Next Scheduled Run: Check EventBridge schedules
{'='*60}
"""
        
        ses_client.send_email(
            Source='mhussain.myindia@gmail.com',
            Destination={'ToAddresses': ['mhussain.myindia@gmail.com']},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        print(f"Comprehensive error email sent successfully")
        
    except Exception as e:
        print(f"Error sending comprehensive error email: {e}")

def save_to_s3_with_path(data, filepath):
    """Save data to S3 with custom path structure"""
    print(f"💾 Saving to S3: {filepath}")
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=filepath,
            Body=json.dumps(data, indent=2),
            ContentType='application/json',
            Metadata={
                'analysis-type': 'swing-trading',
                'created-by': 'lambda-automation',
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        print(f"✅ Saved: {filepath}")
    except Exception as e:
        print(f"❌ Error saving {filepath}: {e}")

def save_to_s3(data, filename):
    """Save analysis data to S3 (legacy function)"""
    save_to_s3_with_path(data, f"analysis/{filename}")

def lambda_handler(event, context):
    """Main Lambda handler"""
    print("🎯 Lambda handler started")
    print(f"📥 Received event: {json.dumps(event, indent=2)}")
    print(f"🔧 Context: {context}")
    
    if not API_KEY or not SECRET_KEY:
        print("❌ API keys not configured")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'API keys not configured'})
        }
    
    print("✅ API keys are configured")
    
    # Symbols to analyze
    symbols = event.get('symbols', ['AAPL', 'NVDA', 'MSFT', 'AMD', 'TSLA', 'ARKK', 'BOTZ', 'QQQ'])
    print(f"📈 Symbols to analyze: {symbols}")
    results = []
    
    for i, symbol in enumerate(symbols, 1):
        print(f"\n🔄 Processing symbol {i}/{len(symbols)}: {symbol}")
        try:
            # Fetch price data
            prices = get_bars(symbol)
            if not prices:
                print(f"⚠️ No price data received for {symbol}, skipping...")
                continue
            
            print(f"✅ Retrieved {len(prices)} price points for {symbol}")
            
            # Calculate indicators
            rsi = calculate_rsi(prices)
            ema = calculate_ema(prices)
            current_price = prices[-1]
            
            print(f"📊 Technical Analysis for {symbol}:")
            print(f"   💰 Current Price: ${current_price:.2f}")
            print(f"   📈 RSI: {rsi:.2f}")
            print(f"   📊 EMA: ${ema:.2f}")
            
            # Generate signal
            print(f"🎯 Signal Logic for {symbol}:")
            print(f"   RSI < 30? {rsi < 30} (RSI: {rsi:.2f})")
            print(f"   Price > EMA? {current_price > ema} (${current_price:.2f} vs ${ema:.2f})")
            print(f"   RSI > 70? {rsi > 70} (RSI: {rsi:.2f})")
            print(f"   Price < EMA? {current_price < ema} (${current_price:.2f} vs ${ema:.2f})")
            
            if rsi < 30 and current_price > ema:
                signal = "BUY"
                print(f"🟢 BUY signal generated for {symbol}")
            elif rsi > 70 and current_price < ema:
                signal = "SELL"
                print(f"🔴 SELL signal generated for {symbol}")
            else:
                signal = "HOLD"
                print(f"🟡 HOLD signal generated for {symbol}")
            
            # Prepare detailed result with historical data
            result = {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'analysis_date': datetime.utcnow().strftime('%Y-%m-%d'),
                'current_price': round(current_price, 2),
                'rsi': round(rsi, 2),
                'ema': round(ema, 2),
                'signal': signal,
                'signal_strength': 'STRONG' if (rsi < 25 or rsi > 75) else 'MODERATE',
                'price_vs_ema': round(((current_price - ema) / ema) * 100, 2),  # % above/below EMA
                'historical_prices': prices[-10:],  # Last 10 days for trend analysis
                'price_range_30d': {
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2),
                    'avg': round(sum(prices) / len(prices), 2)
                },
                'technical_indicators': {
                    'rsi_oversold': rsi < 30,
                    'rsi_overbought': rsi > 70,
                    'price_above_ema': current_price > ema,
                    'price_below_ema': current_price < ema
                }
            }
            
            results.append(result)
            print(f"✅ {symbol} analysis complete: {signal}")
            
            # Individual signal emails removed - comprehensive email sent at end
            
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
            import traceback
            print(f"📋 Full traceback: {traceback.format_exc()}")
            continue
    
    print(f"\n📊 Analysis Summary:")
    print(f"   Total symbols processed: {len(results)}")
    for result in results:
        print(f"   {result['symbol']}: {result['signal']} (RSI: {result['rsi']}, Price: ${result['current_price']})")
    
    # Save results to S3 with organized structure
    if results:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        date_folder = datetime.utcnow().strftime('%Y/%m')
        
        # Save daily analysis
        analysis_filename = f"daily-analysis/{date_folder}/analysis_{timestamp}.json"
        print(f"\n💾 Saving daily analysis to S3...")
        save_to_s3_with_path(results, analysis_filename)
        
        # Save individual symbol data for trend analysis
        for result in results:
            symbol_filename = f"symbols/{result['symbol']}/{date_folder}/{result['symbol']}_{timestamp}.json"
            save_to_s3_with_path(result, symbol_filename)
        
        # Save signals only (for performance tracking)
        signals_only = [r for r in results if r['signal'] in ['BUY', 'SELL']]
        if signals_only:
            signals_filename = f"signals/{date_folder}/signals_{timestamp}.json"
            save_to_s3_with_path(signals_only, signals_filename)
            print(f"🚨 Saved {len(signals_only)} trading signals for future analysis")
        
        # Send comprehensive daily analysis email (always send)
        send_comprehensive_daily_email(results)
    else:
        print("⚠️ No results to save to S3")
        # Save error log and send comprehensive error email
        error_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'error': 'No market data available',
            'symbols_attempted': symbols,
            'analysis_date': datetime.utcnow().strftime('%Y-%m-%d')
        }
        error_filename = f"errors/{datetime.utcnow().strftime('%Y/%m')}/error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        save_to_s3_with_path(error_log, error_filename)
        send_comprehensive_error_email(symbols, error_log)
    
    final_response = {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Processed {len(results)} symbols',
            'results': results
        })
    }
    
    print(f"\n🎯 Lambda execution completed successfully")
    print(f"📤 Final response: {json.dumps(final_response, indent=2)}")
    
    return final_response