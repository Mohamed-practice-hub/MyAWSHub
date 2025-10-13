import boto3
import json
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error
import os
import time
import hashlib
import hmac
from datetime import datetime

# Simple logger
def log(msg, level='INFO'):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"{ts} [{level}] {msg}")

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
TRADING_URL = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}
ses_client = boto3.client('ses')
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')

# Safety / config
AUTO_EXECUTE = os.environ.get('AUTO_EXECUTE', 'false').lower() == 'true'
MIN_CONFIDENCE = float(os.environ.get('MIN_CONFIDENCE', '0.0'))
DDB_TABLE = os.environ.get('WEBHOOK_IDEMPOTENCY_TABLE', 'swing-webhook-events')
ID_TTL_SECONDS = int(os.environ.get('WEBHOOK_ID_TTL', '3600'))
HMAC_SECRET = os.environ.get('WEBHOOK_HMAC_SECRET')  # optional

# DynamoDB table object (if exists)
try:
    id_table = dynamodb.Table(DDB_TABLE)
except Exception:
    id_table = None

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
        if not AUTO_EXECUTE:
            log(f"AUTO_EXECUTE is false; skipping real order for {symbol} {side} {qty}", level='INFO')
            # simulate order response
            return {"id": None, "status": "simulated", "symbol": symbol, "qty": qty, 'order_data': order_data}

        # Use requests if available, otherwise urllib fallback
        if REQUESTS_AVAILABLE:
            response = requests.post(url, headers=HEADERS, json=order_data, timeout=30)
            response.raise_for_status()
            return response.json()
        else:
            req = _urllib_request.Request(url, data=bytes(json.dumps(order_data), 'utf-8'), headers={**HEADERS, 'Content-Type': 'application/json'}, method='POST')
            with _urllib_request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
    except Exception as e:
        log(f"Error placing {side} order for {symbol}: {e}", level='ERROR')
        return {"error": str(e)}

def get_account_buying_power():
    url = f"{TRADING_URL}/v2/account"
    try:
        if REQUESTS_AVAILABLE:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
        else:
            req = _urllib_request.Request(url, headers=HEADERS, method='GET')
            with _urllib_request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
        return float(data.get('buying_power', 0)), float(data.get('cash', 0))
    except Exception as e:
        log(f"Error fetching account info: {e}", level='ERROR')
        return 0.0, 0.0

def send_webhook_email(webhook_data, trade_results):
    """Send webhook execution email"""
    trades = trade_results.get('trades', [])
    successful_trades = [t for t in trades if t.get('success')]
    
    subject = f"🔗 WEBHOOK TRADE - {len(successful_trades)} EXECUTED - {datetime.utcnow().strftime('%Y-%m-%d')}"
    
    body = f"""
WEBHOOK TRADING EXECUTION
{'='*60}
Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Trigger: External Webhook Signal

WEBHOOK DATA RECEIVED:
{'-'*40}
Symbol: {webhook_data.get('symbol', 'N/A')}
Action: {webhook_data.get('action', 'N/A')}
Quantity: {webhook_data.get('qty', 1)}
Source: {webhook_data.get('source', 'Unknown')}
Timestamp: {webhook_data.get('timestamp', 'N/A')}

TRADE EXECUTION RESULTS:
{'-'*40}
Total Orders: {len(trades)}
Successful: {len(successful_trades)}
Failed: {len(trades) - len(successful_trades)}
"""
    
    for trade in trades:
        status = "✅ SUCCESS" if trade.get('success') else "❌ FAILED"
        body += f"""
{status} {trade['action']} {trade['symbol']}
  Order ID: {trade.get('order_id', 'N/A')}
  Status: {trade.get('order_status', 'N/A')}
  Quantity: {trade.get('qty', 1)} shares
  Error: {trade.get('error', 'None')}
"""
    
    body += f"""

WEBHOOK VALIDATION:
{'-'*40}
Valid Symbol: {'✅' if webhook_data.get('symbol') else '❌'}
Valid Action: {'✅' if webhook_data.get('action') in ['BUY', 'SELL'] else '❌'}
Valid Quantity: {'✅' if isinstance(webhook_data.get('qty'), int) and webhook_data.get('qty') > 0 else '❌'}

{'='*60}
AWS WEBHOOK TRADING SYSTEM
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
        print("Webhook email sent successfully")
    except Exception as e:
        print(f"Error sending webhook email: {e}")

def save_webhook_log(webhook_data, trade_results):
    """Save webhook execution to S3"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'webhook_data': webhook_data,
        'trade_results': trade_results,
        'execution_type': 'webhook'
    }
    
    try:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        key = f"webhook-trades/{datetime.utcnow().strftime('%Y/%m')}/webhook_{timestamp}.json"
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(log_data, indent=2),
            ContentType='application/json'
        )
        print(f"Webhook log saved to S3: {key}")
    except Exception as e:
        print(f"Error saving webhook log: {e}")

def lambda_handler(event, context):
    """Handle webhook trading requests"""
    log("Webhook Trading Lambda started")
    log(f"Event: {json.dumps(event)}")

    # attach request id
    request_id = getattr(context, 'aws_request_id', 'N/A')
    
    # Acknowledge receipt immediately for Finnhub
    headers = event.get('headers', {}) if isinstance(event.get('headers', {}), dict) else {}
    if headers.get('X-Finnhub-Secret') == os.environ.get('FINNHUB_SECRET', 'd3l5chpr01qq28em0po0'):
        log('Finnhub webhook authenticated')
    
    # Parse webhook data
    try:
        # Handle both direct invocation and API Gateway
        if 'body' in event:
            # API Gateway format
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            # Direct invocation format
            body = event
        
        # Handle Finnhub webhook format
        if 'data' in body:
            # Finnhub sends data array
            finnhub_data = body['data'][0] if body['data'] else {}
            webhook_data = {
                'symbol': finnhub_data.get('s', body.get('symbol', '')).upper(),
                'action': body.get('action', 'BUY').upper(),  # Default action
                'qty': int(body.get('qty', 1)),
                'source': 'finnhub',
                'timestamp': datetime.utcnow().isoformat(),
                'price': finnhub_data.get('p', 0),
                'volume': finnhub_data.get('v', 0)
            }
        else:
            # Standard webhook format
            webhook_data = {
                'symbol': body.get('symbol', '').upper(),
                'action': body.get('action', '').upper(),
                'qty': int(body.get('qty', 1)),
                'source': body.get('source', 'webhook'),
                'timestamp': body.get('timestamp', datetime.utcnow().isoformat())
            }

        log(f"Parsed webhook data: {webhook_data}")

    except Exception as e:
        error_msg = f"Error parsing webhook data: {e}"
        print(error_msg)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': error_msg})
        }
    
    # HMAC verification for non-Finnhub callers (optional)
    if HMAC_SECRET and 'X-Signature' in headers:
        signature = headers.get('X-Signature')
        computed = hmac.new(HMAC_SECRET.encode(), json.dumps(body if 'body' in event else event).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, computed):
            log('HMAC signature mismatch', level='ERROR')
            return {'statusCode': 403, 'body': json.dumps({'error': 'Invalid signature'})}
    
    # Compute idempotency key (hash of payload)
    raw_payload = json.dumps(body if 'body' in event else event, sort_keys=True)
    event_id = hashlib.sha256(raw_payload.encode()).hexdigest()

    # Idempotency check in DynamoDB
    if id_table is not None:
        try:
            resp = id_table.get_item(Key={'event_id': event_id})
            if 'Item' in resp:
                log(f"Duplicate webhook event detected: {event_id}. Skipping execution.")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Duplicate event - skipped', 'event_id': event_id})
                }
        except Exception as e:
            log(f"Error checking idempotency table: {e}", level='ERROR')

    # Validate webhook data
    if not webhook_data['symbol']:
        return {
            'statusCode': 200,  # Return 200 for Finnhub
            'body': json.dumps({'message': 'No symbol provided, skipping trade'})
        }
    
    if webhook_data['action'] not in ['BUY', 'SELL']:
        return {
            'statusCode': 200,  # Return 200 for Finnhub
            'body': json.dumps({'message': 'No valid action, skipping trade'})
        }
    
    if webhook_data['qty'] <= 0:
        return {
            'statusCode': 200,  # Return 200 for Finnhub
            'body': json.dumps({'message': 'Invalid quantity, skipping trade'})
        }
    
    # Confidence filter
    confidence = float(webhook_data.get('confidence', 1.0))
    if confidence < MIN_CONFIDENCE:
        log(f"Webhook confidence {confidence} below MIN_CONFIDENCE {MIN_CONFIDENCE}; skipping execution", level='WARNING')
        save_webhook_log(webhook_data, {'trades': [], 'summary': {'total_orders': 0, 'successful_orders': 0, 'failed_orders': 0}, 'note': 'low_confidence'})
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Low confidence - skipped', 'confidence': confidence})
        }

    # Execute trade
    trades = []
    log(f"Preparing to execute {webhook_data['action']} order for {webhook_data['symbol']}")

    # Suggested price calculations (optional)
    # Accept optional percentages in webhook payload: stop_loss_pct, limit_pct, trailing_stop_pct
    stop_loss_pct = float(webhook_data.get('stop_loss_pct', 0))
    limit_pct = float(webhook_data.get('limit_pct', 0))
    trailing_stop_pct = float(webhook_data.get('trailing_stop_pct', 0))

    current_price = None
    if webhook_data.get('price'):
        try:
            current_price = float(webhook_data.get('price'))
        except Exception:
            current_price = None

    # If price not provided, try to fetch a quick quote via Alpaca data endpoint (best-effort)
    if current_price is None:
        try:
            quote_url = f"https://data.alpaca.markets/v2/stocks/{webhook_data['symbol']}/quotes/latest"
            if REQUESTS_AVAILABLE:
                r = requests.get(quote_url, headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    current_price = float(r.json().get('quote', {}).get('ap', 0) or r.json().get('quote', {}).get('bp', 0))
            else:
                req = _urllib_request.Request(quote_url, headers=HEADERS, method='GET')
                with _urllib_request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read().decode())
                    current_price = float(data.get('quote', {}).get('ap', 0) or data.get('quote', {}).get('bp', 0))
        except Exception:
            current_price = None

    suggested = {}
    if current_price:
        if stop_loss_pct > 0:
            if webhook_data['action'] == 'BUY':
                suggested['stop_loss_price'] = round(current_price * (1 - stop_loss_pct / 100.0), 4)
            else:
                suggested['stop_loss_price'] = round(current_price * (1 + stop_loss_pct / 100.0), 4)
        if limit_pct > 0:
            if webhook_data['action'] == 'BUY':
                suggested['limit_price'] = round(current_price * (1 - limit_pct / 100.0), 4)
            else:
                suggested['limit_price'] = round(current_price * (1 + limit_pct / 100.0), 4)
        if trailing_stop_pct > 0:
            # trailing stop stored as percentage to be managed by executor or broker
            suggested['trailing_stop_pct'] = trailing_stop_pct

    # Attach suggested prices to webhook_data for logging and email
    if suggested:
        webhook_data['suggested'] = suggested

    # Buying power check
    buying_power, cash = get_account_buying_power()
    estimated_cost = 0  # optional: approximate cost = qty * current price if price provided
    if webhook_data.get('price'):
        estimated_cost = float(webhook_data.get('price')) * int(webhook_data.get('qty', 1))
    if AUTO_EXECUTE and buying_power > 0 and estimated_cost > buying_power:
        log(f"Insufficient buying power ({buying_power}) for estimated cost {estimated_cost}", level='ERROR')
        save_webhook_log(webhook_data, {'trades': [], 'summary': {'total_orders': 0, 'successful_orders': 0, 'failed_orders': 0}, 'note': 'insufficient_buying_power'})
        return {'statusCode': 200, 'body': json.dumps({'message': 'Insufficient buying power', 'buying_power': buying_power})}

    order_result = place_order(
        webhook_data['symbol'], 
        webhook_data['action'].lower(), 
        webhook_data['qty']
    )
    
    trade_result = {
        'action': webhook_data['action'],
        'symbol': webhook_data['symbol'],
        'qty': webhook_data['qty'],
        'success': 'id' in order_result,
        'order_id': order_result.get('id', 'N/A'),
        'order_status': order_result.get('status', 'N/A'),
        'error': order_result.get('error', None)
    }
    
    trades.append(trade_result)

    # Record idempotency entry
    if id_table is not None:
        try:
            ttl = int(time.time()) + ID_TTL_SECONDS
            id_table.put_item(Item={'event_id': event_id, 'created_at': int(time.time()), 'ttl': ttl})
        except Exception as e:
            log(f"Error writing idempotency entry: {e}", level='ERROR')
    
    # Prepare results
    trade_results = {
        'trades': trades,
        'summary': {
            'total_orders': len(trades),
            'successful_orders': len([t for t in trades if t['success']]),
            'failed_orders': len([t for t in trades if not t['success']])
        }
    }
    
    # Save to S3 and send email
    save_webhook_log(webhook_data, trade_results)
    send_webhook_email(webhook_data, trade_results)
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Webhook processed successfully',
            'webhook_data': webhook_data,
            'trade_results': trade_results
        })
    }