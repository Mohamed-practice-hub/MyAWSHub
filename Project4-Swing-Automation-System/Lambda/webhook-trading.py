import json
import time
import os
import hashlib
import hmac
from datetime import datetime
try:
    import boto3
    BOTO3_AVAILABLE = True
except Exception:
    boto3 = None
    BOTO3_AVAILABLE = False
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error
    import urllib.parse as _urllib_parse
else:
    import urllib.parse as _urllib_parse

# Simple logger
def log(msg, level='INFO'):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"{ts} [{level}] {msg}")


def _request_with_retries(method, url, headers=None, params=None, json_body=None, timeout=10, retries=3):
    backoff = 1
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if REQUESTS_AVAILABLE:
                resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout)
                if resp.status_code < 200 or resp.status_code >= 300:
                    log(f"Alpaca {method} {url} returned status {resp.status_code}: {resp.text}", level='WARNING')
                    resp.raise_for_status()
                return resp.json()
            else:
                if params:
                    url_with_q = f"{url}?{_urllib_parse.urlencode(params)}"
                else:
                    url_with_q = url
                if method.upper() == 'GET':
                    req = _urllib_request.Request(url_with_q, headers=headers or {}, method='GET')
                    with _urllib_request.urlopen(req, timeout=timeout) as r:
                        return json.loads(r.read().decode())
                else:
                    data = json.dumps(json_body or {}).encode('utf-8')
                    req_headers = {**(headers or {}), 'Content-Type': 'application/json'}
                    req = _urllib_request.Request(url_with_q, data=data, headers=req_headers, method=method.upper())
                    with _urllib_request.urlopen(req, timeout=timeout) as r:
                        return json.loads(r.read().decode())
        except Exception as e:
            last_err = e
            log(f"Request attempt {attempt} failed for {url}: {e}", level='ERROR')
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
def get_alpaca_keys():
    """Retrieve Alpaca API keys from env or Secrets Manager (lazy)."""
    api = os.environ.get('ALPACA_API_KEY')
    secret = os.environ.get('ALPACA_SECRET_KEY')
    if api and secret:
        return api, secret
    if not BOTO3_AVAILABLE:
        raise RuntimeError('boto3 not available and ALPACA_* env vars not set')
    client = boto3.client('secretsmanager')
    secret_name = "swing-alpaca/papter-trading/keys"
    try:
        response = client.get_secret_value(SecretId=secret_name)
        sec = json.loads(response['SecretString'])
        return sec['ALPACA_API_KEY'], sec['ALPACA_SECRET_KEY']
    except Exception as e:
        log(f"Error retrieving secrets: {e}", level='ERROR')
        raise

# Lazy constants and getters
TRADING_URL = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
DATA_URL = os.environ.get('ALPACA_DATA_URL', 'https://data.alpaca.markets')
S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')

def get_headers():
    api = os.environ.get('ALPACA_API_KEY')
    secret = os.environ.get('ALPACA_SECRET_KEY')
    if not api or not secret:
        api, secret = get_alpaca_keys()
    return {"APCA-API-KEY-ID": api, "APCA-API-SECRET-KEY": secret}

def get_ses_client():
    if not BOTO3_AVAILABLE:
        return None
    return boto3.client('ses')

def get_s3_client():
    if not BOTO3_AVAILABLE:
        return None
    return boto3.client('s3')

def get_dynamodb_resource():
    if not BOTO3_AVAILABLE:
        return None
    return boto3.resource('dynamodb')

# Safety / config
AUTO_EXECUTE = os.environ.get('AUTO_EXECUTE', 'false').lower() == 'true'
MIN_CONFIDENCE = float(os.environ.get('MIN_CONFIDENCE', '0.0'))
DDB_TABLE = os.environ.get('WEBHOOK_IDEMPOTENCY_TABLE', 'swing-webhook-events')
ID_TTL_SECONDS = int(os.environ.get('WEBHOOK_ID_TTL', '3600'))
HMAC_SECRET = os.environ.get('WEBHOOK_HMAC_SECRET')  # optional
DEBOUNCE_COUNT = int(os.environ.get('DEBOUNCE_COUNT', '2'))
MIN_INTERVAL_SAME_SYMBOL = int(os.environ.get('MIN_INTERVAL_SAME_SYMBOL', str(30*60)))  # seconds
MAX_TRADES_PER_DAY = int(os.environ.get('MAX_TRADES_PER_DAY', '5'))

def get_id_table():
    ddb = get_dynamodb_resource()
    if ddb is None:
        return None
    try:
        return ddb.Table(DDB_TABLE)
    except Exception:
        return None

def place_order(symbol, side, qty=1, order_opts=None):
    """Place buy/sell order via Alpaca Trading API"""
    url = f"{TRADING_URL}/v2/orders"
    
    order_data = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        # default to market; may be altered below
        "type": "market",
        "time_in_force": "day"
    }

    # If order options present and AUTO_EXECUTE is enabled, prepare bracket or limit orders
    if order_opts and AUTO_EXECUTE:
        take_profit = order_opts.get('limit_price')
        stop_loss = order_opts.get('stop_loss_price')
        # If both provided, create a bracket order
        if take_profit and stop_loss:
            order_data['order_class'] = 'bracket'
            # primary order remains market
            order_data['type'] = 'market'
            order_data['take_profit'] = {'limit_price': str(take_profit)}
            order_data['stop_loss'] = {'stop_price': str(stop_loss)}
        # If only limit is provided and side is SELL, consider limit order
        elif take_profit and side == 'sell':
            order_data['type'] = 'limit'
            order_data['limit_price'] = str(take_profit)
        # If only stop_loss provided and side is SELL, place stop order
        elif stop_loss and side == 'sell':
            order_data['type'] = 'stop'
            order_data['stop_price'] = str(stop_loss)
    
    try:
        if not AUTO_EXECUTE:
            log(f"AUTO_EXECUTE is false; skipping real order for {symbol} {side} {qty}", level='INFO')
            # simulate order response
            return {"id": None, "status": "simulated", "symbol": symbol, "qty": qty, 'order_data': order_data}

        headers = get_headers()
        try:
            resp = _request_with_retries('POST', url, headers=headers, json_body=order_data, timeout=30, retries=3)
            return resp
        except Exception as exc:
            log(f"Error placing {side} order for {symbol}: {exc}", level='ERROR')
            return {"error": str(exc)}
    except Exception as e:
        log(f"Unexpected error placing order for {symbol}: {e}", level='ERROR')
        return {"error": str(e)}

def get_account_buying_power():
    url = f"{TRADING_URL}/v2/account"
    try:
        headers = get_headers()
        data = _request_with_retries('GET', url, headers=headers, timeout=10, retries=3)
        return float(data.get('buying_power', 0)), float(data.get('cash', 0))
    except Exception as e:
        log(f"Error fetching account info after retries: {e}", level='ERROR')
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
        ses = get_ses_client()
        if ses is None:
            print('SES client not available (boto3 missing). Email not sent.')
        else:
            ses.send_email(
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
        s3 = get_s3_client()
        if s3 is None:
            print('S3 client not available (boto3 missing). Skipping S3 save.')
        else:
            s3.put_object(
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
    # Stable event id: hash(symbol+action+qty+source) to avoid timestamp differences
    stable_key = f"{webhook_data['symbol']}|{webhook_data['action']}|{webhook_data['qty']}|{webhook_data.get('source','') }"
    event_id = hashlib.sha256(stable_key.encode()).hexdigest()

    # Keys for additional bookkeeping in DynamoDB
    symbol_key = f"symbol::{webhook_data['symbol']}"
    debounce_key = f"debounce::{event_id}"
    daily_counter_key = f"daily::{webhook_data['symbol']}::{datetime.utcnow().strftime('%Y-%m-%d')}"

    # Idempotency check in DynamoDB
    id_table = get_id_table()
    if id_table is not None:
        try:
            # Check stable dedupe
            resp = id_table.get_item(Key={'event_id': event_id})
            if 'Item' in resp:
                log(f"Duplicate webhook event detected: {event_id}. Skipping execution.")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Duplicate event - skipped', 'event_id': event_id})
                }

            # Check per-symbol daily limit
            daily_resp = id_table.get_item(Key={'event_id': daily_counter_key})
            today_count = int(daily_resp.get('Item', {}).get('count', 0)) if 'Item' in daily_resp else 0
            if today_count >= MAX_TRADES_PER_DAY:
                log(f"Max trades per day reached for {webhook_data['symbol']}: {today_count}", level='WARNING')
                save_webhook_log(webhook_data, {'trades': [], 'summary': {}, 'note': 'max_trades_reached'})
                return {'statusCode': 200, 'body': json.dumps({'message': 'Max trades per day reached'})}

            # Check min interval for this symbol
            sym_resp = id_table.get_item(Key={'event_id': symbol_key})
            if 'Item' in sym_resp:
                last_ts = int(sym_resp['Item'].get('last_executed_at', 0))
                if int(time.time()) - last_ts < MIN_INTERVAL_SAME_SYMBOL:
                    log(f"Trade for {webhook_data['symbol']} skipped: min-interval not passed", level='WARNING')
                    save_webhook_log(webhook_data, {'trades': [], 'summary': {}, 'note': 'min_interval_not_passed'})
                    return {'statusCode': 200, 'body': json.dumps({'message': 'Min interval not passed'})}

            # Debounce logic: increment debounce counter; require DEBOUNCE_COUNT hits before execution
            debounce_resp = id_table.get_item(Key={'event_id': debounce_key})
            debounce_count = int(debounce_resp.get('Item', {}).get('count', 0)) if 'Item' in debounce_resp else 0
            debounce_count += 1
            # write/update debounce counter with TTL (short lived)
            ttl = int(time.time()) + 300  # 5 minutes window
            id_table.put_item(Item={'event_id': debounce_key, 'count': debounce_count, 'ttl': ttl})
            if debounce_count < DEBOUNCE_COUNT:
                log(f"Debounce: seen {debounce_count}/{DEBOUNCE_COUNT} for {stable_key}; waiting for more signals", level='INFO')
                save_webhook_log(webhook_data, {'trades': [], 'summary': {}, 'note': 'debounce_waiting'})
                return {'statusCode': 200, 'body': json.dumps({'message': 'Debounce - waiting for repeated signal', 'count': debounce_count})}
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
            headers = get_headers()
            if REQUESTS_AVAILABLE:
                r = requests.get(quote_url, headers=headers, timeout=5)
                if r.status_code == 200:
                    current_price = float(r.json().get('quote', {}).get('ap', 0) or r.json().get('quote', {}).get('bp', 0))
            else:
                req = _urllib_request.Request(quote_url, headers=headers, method='GET')
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
    id_table = get_id_table()
    if id_table is not None:
        try:
            ttl = int(time.time()) + ID_TTL_SECONDS
            id_table.put_item(Item={'event_id': event_id, 'created_at': int(time.time()), 'ttl': ttl})
            # update symbol last executed timestamp and daily counter
            id_table.put_item(Item={'event_id': symbol_key, 'last_executed_at': int(time.time()), 'ttl': int(time.time()) + (24*3600)})
            # update daily counter
            daily_resp = id_table.get_item(Key={'event_id': daily_counter_key})
            daily_count = int(daily_resp.get('Item', {}).get('count', 0)) if 'Item' in daily_resp else 0
            id_table.put_item(Item={'event_id': daily_counter_key, 'count': daily_count + 1, 'ttl': int(time.time()) + (24*3600)})
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