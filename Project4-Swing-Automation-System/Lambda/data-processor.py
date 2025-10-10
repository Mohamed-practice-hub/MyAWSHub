import boto3
import json
import requests
import os
from datetime import datetime

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

# Initialize outside handler for better performance
try:
    API_KEY, SECRET_KEY = get_alpaca_keys()
    BASE_URL = "https://paper-api.alpaca.markets"
    HEADERS = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY
    }
    s3_client = boto3.client('s3')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'project4-swing-automation-data')
except Exception as e:
    print(f"Initialization error: {e}")
    API_KEY = SECRET_KEY = None

def get_bars(symbol, timeframe="1Day", limit=30):
    """Fetch historical price data from Alpaca"""
    url = f"{BASE_URL}/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": timeframe,
        "limit": limit
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        return [float(bar['c']) for bar in data.get('bars', [])]
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return []

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return 50  # Default neutral RSI
    
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
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(prices, period=20):
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return sum(prices) / len(prices)  # Simple average if not enough data
    
    ema = prices[0]
    multiplier = 2 / (period + 1)
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def save_to_s3(data, filename):
    """Save analysis data to S3"""
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=f"analysis/{filename}",
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        print(f"Data saved to S3: {filename}")
    except Exception as e:
        print(f"Error saving to S3: {e}")

def lambda_handler(event, context):
    """Main Lambda handler"""
    if not API_KEY or not SECRET_KEY:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'API keys not configured'})
        }
    
    # Symbols to analyze
    symbols = event.get('symbols', ['AAPL', 'MSFT', 'GOOGL'])
    results = []
    
    for symbol in symbols:
        try:
            # Fetch price data
            prices = get_bars(symbol)
            if not prices:
                continue
            
            # Calculate indicators
            rsi = calculate_rsi(prices)
            ema = calculate_ema(prices)
            current_price = prices[-1]
            
            # Generate signal
            if rsi < 30 and current_price > ema:
                signal = "BUY"
            elif rsi > 70 and current_price < ema:
                signal = "SELL"
            else:
                signal = "HOLD"
            
            # Prepare result
            result = {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'price': round(current_price, 2),
                'rsi': round(rsi, 2),
                'ema': round(ema, 2),
                'signal': signal
            }
            
            results.append(result)
            print(f"{symbol} | RSI: {rsi:.2f} | EMA: {ema:.2f} | Price: {current_price:.2f} | Signal: {signal}")
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            continue
    
    # Save results to S3
    if results:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        save_to_s3(results, f"analysis_{timestamp}.json")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Processed {len(results)} symbols',
            'results': results
        })
    }