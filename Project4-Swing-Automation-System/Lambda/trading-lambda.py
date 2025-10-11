import boto3
import json
import requests
import os
from datetime import datetime, timedelta

def get_alpaca_keys():
    """Retrieve Alpaca API keys from AWS Secrets Manager"""
    client = boto3.client('secretsmanager')
    secret_name = "swing-alpaca/papter-trading/keys"
    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret['ALPACA_API_KEY'], secret['ALPACA_SECRET_KEY']
    except Exception as e:
        print(f"Error retrieving secrets: {e}")
        raise

# Initialize
API_KEY, SECRET_KEY = get_alpaca_keys()
DATA_URL = "https://data.alpaca.markets"
TRADING_URL = "https://paper-api.alpaca.markets"
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')
S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')

def get_bars(symbol, timeframe="1Day", limit=30):
    """Fetch historical price data"""
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    url = f"{DATA_URL}/v2/stocks/{symbol}/bars"
    params = {"timeframe": timeframe, "limit": limit, "start": start_date}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        bars = data.get('bars', [])
        return [float(bar['c']) for bar in bars] if bars else []
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return []

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    if len(prices) < period + 1:
        return 50
    
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(prices, period=20):
    """Calculate EMA"""
    if len(prices) < period:
        return sum(prices) / len(prices)
    
    ema = prices[0]
    multiplier = 2 / (period + 1)
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def place_order(symbol, side, qty=1):
    """Place buy/sell order via Alpaca Trading API"""
    url = f"{TRADING_URL}/v2/orders"
    
    order_data = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "type": "market",
        "time_in_force": "day"
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=order_data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error placing {side} order for {symbol}: {e}")
        return None

def send_trading_email(trades, analysis_results):
    """Send email with trading results"""
    buy_trades = [t for t in trades if t['side'] == 'buy']
    sell_trades = [t for t in trades if t['side'] == 'sell']
    
    if buy_trades or sell_trades:
        subject = f"🚨 TRADES EXECUTED - {len(buy_trades)} BUY, {len(sell_trades)} SELL - {datetime.utcnow().strftime('%Y-%m-%d')}"
    else:
        subject = f"📊 No Trades - Analysis Complete - {datetime.utcnow().strftime('%Y-%m-%d')}"
    
    body = f"""
AUTOMATED SWING TRADING EXECUTION
{'='*60}
Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Status: COMPLETED

TRADES EXECUTED: {len(trades)}
• BUY Orders: {len(buy_trades)}
• SELL Orders: {len(sell_trades)}

TRADE DETAILS:
{'-'*40}
"""
    
    for trade in trades:
        status = "✅ SUCCESS" if trade.get('status') == 'accepted' else "❌ FAILED"
        body += f"""
{status} {trade['side'].upper()} {trade['symbol']}
  Quantity: {trade['qty']} shares
  Order ID: {trade.get('id', 'N/A')}
  Price: ${trade.get('filled_avg_price', 'Market')}
  Time: {trade.get('created_at', 'N/A')}
"""
    
    body += f"""

ANALYSIS SUMMARY:
{'-'*40}
"""
    
    for result in analysis_results:
        signal_emoji = "🟢" if result['signal'] == 'BUY' else "🔴" if result['signal'] == 'SELL' else "🟡"
        body += f"""
{signal_emoji} {result['symbol']}: {result['signal']}
  Price: ${result['current_price']:.2f} | RSI: {result['rsi']:.2f} | EMA: ${result['ema']:.2f}
"""
    
    body += f"""

{'='*60}
AWS AUTOMATED SWING TRADING SYSTEM
Execution Time: {datetime.utcnow().isoformat()}
{'='*60}
"""
    
    try:
        ses_client.send_email(
            Source='mhussain.myindia@gmail.com',
            Destination={'ToAddresses': ['mhussain.myindia@gmail.com']},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        print("Trading email sent successfully")
    except Exception as e:
        print(f"Error sending trading email: {e}")

def lambda_handler(event, context):
    """Main Lambda handler with trading execution"""
    print("🎯 Trading Lambda started")
    
    symbols = event.get('symbols', ['AAPL', 'NVDA', 'MSFT', 'AMD', 'TSLA', 'ARKK', 'BOTZ', 'QQQ'])
    results = []
    trades = []
    
    for symbol in symbols:
        print(f"Processing {symbol}...")
        
        # Get price data and calculate indicators
        prices = get_bars(symbol)
        if not prices:
            continue
            
        rsi = calculate_rsi(prices)
        ema = calculate_ema(prices)
        current_price = prices[-1]
        
        # Generate signal
        if rsi < 30 and current_price > ema:
            signal = "BUY"
            # Execute BUY order
            order_result = place_order(symbol, "buy", qty=1)
            if order_result:
                trades.append({
                    'symbol': symbol,
                    'side': 'buy',
                    'qty': 1,
                    'status': order_result.get('status'),
                    'id': order_result.get('id'),
                    'created_at': order_result.get('created_at')
                })
                print(f"🟢 BUY order placed for {symbol}")
            
        elif rsi > 70 and current_price < ema:
            signal = "SELL"
            # Execute SELL order
            order_result = place_order(symbol, "sell", qty=1)
            if order_result:
                trades.append({
                    'symbol': symbol,
                    'side': 'sell',
                    'qty': 1,
                    'status': order_result.get('status'),
                    'id': order_result.get('id'),
                    'created_at': order_result.get('created_at')
                })
                print(f"🔴 SELL order placed for {symbol}")
        else:
            signal = "HOLD"
        
        result = {
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat(),
            'current_price': round(current_price, 2),
            'rsi': round(rsi, 2),
            'ema': round(ema, 2),
            'signal': signal
        }
        results.append(result)
    
    # Save results to S3
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    # Save trading results
    trading_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'trades_executed': len(trades),
        'trades': trades,
        'analysis': results
    }
    
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=f"trading-results/{datetime.utcnow().strftime('%Y/%m')}/trades_{timestamp}.json",
        Body=json.dumps(trading_data, indent=2),
        ContentType='application/json'
    )
    
    # Send comprehensive email
    send_trading_email(trades, results)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Processed {len(results)} symbols, executed {len(trades)} trades',
            'trades': trades,
            'results': results
        })
    }