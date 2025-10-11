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

def send_email(subject, body):
    """Send email notification via SES"""
    print(f"📧 Sending email: {subject}")
    try:
        ses_client.send_email(
            Source='mhussain.myindia@outlook.com',
            Destination={'ToAddresses': ['mhussain.myindia@outlook.com']},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        print(f"✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

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
    symbols = event.get('symbols', ['AAPL', 'NVDA', 'MSFT', 'AMD', 'TSLA'])
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
            
            # Send email for BUY/SELL signals only
            if signal in ['BUY', 'SELL']:
                email_subject = f"🚨 Swing Signal Alert: {symbol} - {signal}"
                email_body = f"""Swing Trading Signal Generated:

Symbol: {symbol}
Signal: {signal}
Price: ${current_price:.2f}
RSI: {rsi:.2f}
EMA: ${ema:.2f}
Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Signal Logic:
- RSI < 30 (Oversold): {rsi < 30}
- Price > EMA (Uptrend): {current_price > ema}
- RSI > 70 (Overbought): {rsi > 70}
- Price < EMA (Downtrend): {current_price < ema}

This is an automated alert from your swing trading bot."""
                send_email(email_subject, email_body)
            
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
        
        # Send daily summary email
        buy_signals = [r for r in results if r['signal'] == 'BUY']
        sell_signals = [r for r in results if r['signal'] == 'SELL']
        
        if buy_signals or sell_signals:
            summary_subject = f"📊 Daily Swing Analysis Summary - {len(buy_signals)} BUY, {len(sell_signals)} SELL"
            summary_body = f"""Daily Swing Trading Analysis Complete:

Total Symbols Analyzed: {len(results)}
BUY Signals: {len(buy_signals)}
SELL Signals: {len(sell_signals)}
HOLD Signals: {len(results) - len(buy_signals) - len(sell_signals)}

Detailed Results:
"""
            for result in results:
                summary_body += f"\n{result['symbol']}: {result['signal']} (Price: ${result['current_price']}, RSI: {result['rsi']}, EMA: ${result['ema']:.2f})"
            
            summary_body += f"\n\nAnalysis completed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            send_email(summary_subject, summary_body)
    else:
        print("⚠️ No results to save to S3")
        # Save error log for tracking
        error_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'error': 'No market data available',
            'symbols_attempted': symbols,
            'analysis_date': datetime.utcnow().strftime('%Y-%m-%d')
        }
        error_filename = f"errors/{datetime.utcnow().strftime('%Y/%m')}/error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        save_to_s3_with_path(error_log, error_filename)
        send_email("⚠️ Swing Analysis - No Data", "No market data was available for analysis today.")
    
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