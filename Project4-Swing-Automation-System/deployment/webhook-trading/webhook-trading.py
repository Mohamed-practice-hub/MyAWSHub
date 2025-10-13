import boto3
import json
import os
import time
import hashlib
from datetime import datetime, timezone, timedelta

try:
    import requests
except Exception:
    # Fallback to urllib if requests isn't available at runtime
    requests = None  # Will be guarded in _request_with_retries

def _now_utc():
    return datetime.now(timezone.utc)

def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()

def _request_with_retries(method: str, url: str, *, headers=None, json_body=None, params=None, timeout=10, max_retries=3, backoff_factor=0.5):
    """HTTP helper with basic retry/backoff and error-body logging. Uses requests if available, else urllib."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            if requests is None:
                import urllib.request
                req = urllib.request.Request(url, method=method.upper())
                if headers:
                    for k, v in headers.items():
                        req.add_header(k, v)
                if json_body is not None:
                    data = json.dumps(json_body).encode('utf-8')
                    req.add_header('Content-Type', 'application/json')
                else:
                    data = None
                with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
                    body = resp.read().decode('utf-8')
                    status = resp.getcode()
                    if status < 200 or status >= 300:
                        print(f"Non-2xx response from {url}: {status} body={body[:500]}")
                    return status, json.loads(body) if body else {}
            else:
                func = requests.request
                resp = func(method.upper(), url, headers=headers, json=json_body, params=params, timeout=timeout)
                text = resp.text or ''
                if resp.status_code < 200 or resp.status_code >= 300:
                    print(f"Non-2xx response from {url}: {resp.status_code} body={text[:500]}")
                return resp.status_code, (resp.json() if text else {})
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                sleep_for = backoff_factor * (2 ** attempt)
                print(f"HTTP error on {method} {url}: {e}; retrying in {sleep_for:.1f}s ({attempt+1}/{max_retries})")
                time.sleep(sleep_for)
            else:
                print(f"HTTP failed after retries: {e}")
                raise

# Lazy AWS clients and config
_secrets_client = None
_ses_client = None
_s3_client = None

def get_secrets_client():
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client('secretsmanager')
    return _secrets_client

def get_ses_client():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client('ses')
    return _ses_client

def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client

def get_alpaca_keys():
    """Retrieve Alpaca API keys from AWS Secrets Manager (lazy)."""
    secret_name = os.environ.get('ALPACA_SECRET_NAME', "swing-alpaca/papter-trading/keys")
    try:
        response = get_secrets_client().get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret['ALPACA_API_KEY'], secret['ALPACA_SECRET_KEY']
    except Exception as e:
        print(f"Error retrieving secrets '{secret_name}': {e}")
        raise

def get_headers():
    api_key, secret_key = get_alpaca_keys()
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }

# Config
TRADING_URL = os.environ.get('ALPACA_TRADING_URL', "https://paper-api.alpaca.markets")
S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')

# Guardrails
AUTO_EXECUTE = os.environ.get('AUTO_EXECUTE', 'true').lower() == 'true'
DEBOUNCE_SECONDS = int(os.environ.get('DEBOUNCE_SECONDS', '30'))
MIN_INTERVAL_SAME_SYMBOL_SECONDS = int(os.environ.get('MIN_INTERVAL_SAME_SYMBOL_SECONDS', '300'))
MAX_TRADES_PER_DAY = int(os.environ.get('MAX_TRADES_PER_DAY', '10'))

def _state_key_recent(event_hash: str) -> str:
    return f"state/recent/{event_hash}.marker"

def _state_key_symbol(symbol: str) -> str:
    return f"state/last-trade/{symbol}.json"

def _state_key_daily_counts(date_str: str) -> str:
    return f"state/daily-counts/{date_str}.json"

def _s3_read_json(key: str):
    try:
        resp = get_s3_client().get_object(Bucket=S3_BUCKET, Key=key)
        data = resp['Body'].read().decode('utf-8')
        return json.loads(data)
    except Exception as e:
        return None

def _s3_write_json(key: str, data: dict):
    try:
        get_s3_client().put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        print(f"Error writing S3 state {key}: {e}")
        return False

def _s3_object_exists(key: str):
    try:
        get_s3_client().head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except Exception:
        return False

def _event_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def check_debounce_and_limits(webhook_data: dict):
    """Enforce debounce, per-symbol min interval, and daily max trades using S3 state.
    Returns (ok: bool, reason: str)."""
    now = _now_utc()
    date_str = now.strftime('%Y-%m-%d')
    symbol = webhook_data.get('symbol', '').upper()

    # Debounce identical events for a brief period
    ev_hash = _event_hash(webhook_data)
    recent_key = _state_key_recent(ev_hash)
    try:
        if _s3_object_exists(recent_key):
            # Check last modified
            head = get_s3_client().head_object(Bucket=S3_BUCKET, Key=recent_key)
            last_mod = head['LastModified']  # datetime
            age = (now - last_mod).total_seconds()
            if age < DEBOUNCE_SECONDS:
                return False, f"Debounced duplicate event (age {age:.0f}s < {DEBOUNCE_SECONDS}s)"
        # Touch marker
        get_s3_client().put_object(Bucket=S3_BUCKET, Key=recent_key, Body=b'1', ContentType='text/plain')
    except Exception as e:
        print(f"Debounce check error (continuing): {e}")

    # Per-symbol minimum interval
    sym_key = _state_key_symbol(symbol)
    sym_state = _s3_read_json(sym_key) or {}
    last_ts = sym_state.get('last_trade_ts')
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            age = (now - last_dt).total_seconds()
            if age < MIN_INTERVAL_SAME_SYMBOL_SECONDS:
                return False, f"Symbol {symbol} min-interval not met ({age:.0f}s < {MIN_INTERVAL_SAME_SYMBOL_SECONDS}s)"
        except Exception:
            pass

    # Daily max trades
    day_key = _state_key_daily_counts(date_str)
    daily = _s3_read_json(day_key) or {"total": 0}
    if int(daily.get('total', 0)) >= MAX_TRADES_PER_DAY:
        return False, f"Daily trade cap reached ({daily.get('total')} >= {MAX_TRADES_PER_DAY})"

    return True, "OK"

def record_trade_success(webhook_data: dict):
    now = _now_utc()
    date_str = now.strftime('%Y-%m-%d')
    symbol = webhook_data.get('symbol', '').upper()

    # Update last trade per symbol
    sym_key = _state_key_symbol(symbol)
    _s3_write_json(sym_key, {"last_trade_ts": _iso(now)})

    # Increment daily count
    day_key = _state_key_daily_counts(date_str)
    current = _s3_read_json(day_key) or {"total": 0}
    current['total'] = int(current.get('total', 0)) + 1
    _s3_write_json(day_key, current)

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
        status, data = _request_with_retries('POST', url, headers=get_headers(), json_body=order_data, timeout=10, max_retries=2)
        if 200 <= status < 300:
            return data
        return {"error": data or {"status": status}}
    except Exception as e:
        print(f"Error placing {side} order for {symbol}: {e}")
        return {"error": str(e)}

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
        get_ses_client().send_email(
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

        get_s3_client().put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(log_data, indent=2),
            ContentType='application/json'
        )
        print(f"Webhook log saved to S3: {key}")
    except Exception as e:
        print(f"Error saving webhook log: {e}")

CODE_VERSION = "webhook-trading/2025-10-13-iter2"

def lambda_handler(event, context):
    """Handle webhook trading requests"""
    print(f"🔗 Webhook Trading Lambda started - {CODE_VERSION}")
    print(f"Event: {json.dumps(event, indent=2)}")
    
    # Acknowledge receipt immediately for Finnhub
    if event.get('headers', {}).get('X-Finnhub-Secret') == 'd3l5chpr01qq28em0po0':
        print("✅ Finnhub webhook authenticated")
    
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
        
        print(f"Parsed webhook data: {webhook_data}")
        
    except Exception as e:
        error_msg = f"Error parsing webhook data: {e}"
        print(error_msg)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': error_msg})
        }
    
    # Return 200 immediately for Finnhub acknowledgment
    if event.get('headers', {}).get('X-Finnhub-Secret'):
        # Process in background, return success immediately
        pass
    
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
    
    # Guardrails: debounce and rate limits
    ok, reason = check_debounce_and_limits(webhook_data)
    if not ok:
        print(f"Skipping trade due to guardrails: {reason}")
        save_webhook_log(webhook_data, {'trades': [], 'summary': {'total_orders': 0, 'successful_orders': 0, 'failed_orders': 0}, 'skipped': reason})
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f'Skipped: {reason}', 'webhook_data': webhook_data})
        }

    # Execute trade
    trades = []
    
    print(f"Executing {webhook_data['action']} order for {webhook_data['symbol']}")
    execute = AUTO_EXECUTE and (not bool(event.get('dry_run')))
    if execute:
        order_result = place_order(
            webhook_data['symbol'], 
            webhook_data['action'].lower(), 
            webhook_data['qty']
        )
    else:
        order_result = {"id": "dry-run", "status": "simulated", "symbol": webhook_data['symbol']}
    
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
    if trade_result['success']:
        record_trade_success(webhook_data)
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