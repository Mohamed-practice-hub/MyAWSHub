import json
import time
import urllib.parse as _urllib_parse
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
    import urllib.parse as _urllib_parse
    import urllib.error as _urllib_error

def http_get(url, headers=None, params=None, timeout=10):
    """Simple GET helper using requests if available, otherwise urllib"""
    if params:
        query = _urllib_parse.urlencode(params)
        url = f"{url}?{query}"

    if REQUESTS_AVAILABLE:
        resp = requests.get(url, headers=headers, params=None, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    else:
        req_headers = headers or {}
        req = _urllib_request.Request(url, headers=req_headers, method='GET')
        with _urllib_request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())


def _request_with_retries(method, url, headers=None, params=None, json_body=None, timeout=10, retries=3):
    """Make HTTP requests with simple retries and exponential backoff. Returns parsed JSON on success or raises the last exception."""
    backoff = 1
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if REQUESTS_AVAILABLE:
                resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout)
                # Log non-2xx for visibility
                if resp.status_code < 200 or resp.status_code >= 300:
                    print(f"Alpaca {method} {url} returned status {resp.status_code}: {resp.text}")
                    resp.raise_for_status()
                return resp.json()
            else:
                # fallback: support GET and POST
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
            print(f"Request attempt {attempt} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
            else:
                # re-raise the last exception for the caller to handle
                raise
import os
from datetime import datetime, timedelta
from datetime import timezone

def get_alpaca_keys():
    """Retrieve Alpaca API keys from AWS Secrets Manager"""
    # Prefer environment variables for local testing
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
        secret_obj = json.loads(response['SecretString'])
        return secret_obj['ALPACA_API_KEY'], secret_obj['ALPACA_SECRET_KEY']
    except Exception as e:
        print(f"Error retrieving secrets: {e}")
        raise

# Constants and lazy clients
TRADING_URL = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
DATA_URL = os.environ.get('ALPACA_DATA_URL', 'https://data.alpaca.markets')

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

def get_account_info():
    """Get account information"""
    url = f"{TRADING_URL}/v2/account"
    try:
        headers = get_headers()
        return _request_with_retries('GET', url, headers=headers, timeout=10, retries=3)
    except Exception as e:
        print(f"Error getting account info after retries: {e}")
        return None

def get_positions():
    """Get current positions"""
    url = f"{TRADING_URL}/v2/positions"
    try:
        headers = get_headers()
        return _request_with_retries('GET', url, headers=headers, timeout=10, retries=3)
    except Exception as e:
        print(f"Error getting positions after retries: {e}")
        return []

def get_orders(status="all", limit=50):
    """Get recent orders"""
    url = f"{TRADING_URL}/v2/orders"
    params = {"status": status, "limit": limit, "direction": "desc"}
    try:
        headers = get_headers()
        return _request_with_retries('GET', url, headers=headers, params=params, timeout=10, retries=3)
    except Exception as e:
        print(f"Error getting orders after retries: {e}")
        return []

def get_current_price(symbol):
    """Get current price for symbol"""
    url = f"{DATA_URL}/v2/stocks/{symbol}/trades/latest"
    try:
        headers = get_headers()
        data = _request_with_retries('GET', url, headers=headers, timeout=5, retries=2)
        return data.get('trade', {}).get('p', 0)
    except Exception as e:
        print(f"Error getting price for {symbol} after retries: {e}")
        return 0

def send_portfolio_report(account, positions, recent_orders):
    """Send comprehensive portfolio report"""
    
    # Calculate totals
    total_value = float(account.get('portfolio_value', 0))
    total_pnl = float(account.get('unrealized_pl', 0))
    buying_power = float(account.get('buying_power', 0))
    
    # Count positions
    long_positions = [p for p in positions if float(p['qty']) > 0]
    short_positions = [p for p in positions if float(p['qty']) < 0]
    
    # Recent trades
    filled_orders = [o for o in recent_orders if o.get('status') == 'filled']
    today_orders = [o for o in filled_orders if o.get('filled_at', '').startswith(datetime.utcnow().strftime('%Y-%m-%d'))]
    
    subject = f"📊 Portfolio Report - ${total_value:,.2f} ({'+' if total_pnl >= 0 else ''}${total_pnl:,.2f}) - {datetime.utcnow().strftime('%Y-%m-%d')}"
    
    body = f"""
SWING TRADING PORTFOLIO REPORT
{'='*60}
Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

ACCOUNT SUMMARY:
{'-'*40}
Portfolio Value: ${total_value:,.2f}
Unrealized P&L: ${total_pnl:,.2f} ({'+' if total_pnl >= 0 else ''}{(total_pnl/total_value)*100:.2f}%)
Buying Power: ${buying_power:,.2f}
Day Trade Count: {account.get('daytrade_count', 0)}

CURRENT POSITIONS: {len(positions)}
{'-'*40}
Long Positions: {len(long_positions)}
Short Positions: {len(short_positions)}
"""
    
    if positions:
        body += "\nPOSITION DETAILS:\n"
        for pos in positions:
            symbol = pos['symbol']
            qty = float(pos['qty'])
            avg_price = float(pos['avg_entry_price'])
            current_price = get_current_price(symbol)
            market_value = float(pos['market_value'])
            unrealized_pl = float(pos['unrealized_pl'])
            unrealized_pct = float(pos['unrealized_plpc']) * 100
            
            position_type = "LONG" if qty > 0 else "SHORT"
            pnl_emoji = "🟢" if unrealized_pl >= 0 else "🔴"
            
            body += f"""
{pnl_emoji} {symbol} ({position_type})
  Quantity: {qty:,.0f} shares
  Avg Entry: ${avg_price:.2f}
  Current: ${current_price:.2f}
  Market Value: ${market_value:,.2f}
  P&L: ${unrealized_pl:,.2f} ({unrealized_pct:+.2f}%)
"""
    
    body += f"""

TODAY'S TRADING ACTIVITY: {len(today_orders)}
{'-'*40}
"""
    
    if today_orders:
        for order in today_orders[:10]:  # Show last 10 trades
            side_emoji = "🟢" if order['side'] == 'buy' else "🔴"
            filled_price = float(order.get('filled_avg_price', 0))
            body += f"""
{side_emoji} {order['side'].upper()} {order['symbol']}
  Quantity: {order['filled_qty']} shares
  Price: ${filled_price:.2f}
  Time: {order.get('filled_at', 'N/A')[:19]}
  Order ID: {order.get('id', 'N/A')[:8]}...
"""
    else:
        body += "\nNo trades executed today.\n"
    
    # Normalize comparison to timezone-aware UTC datetimes
    now_utc = datetime.now(timezone.utc)
    recent_count = 0
    for o in recent_orders:
        created_str = o.get('created_at', '2020-01-01T00:00:00')
        try:
            created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
        except Exception:
            # fallback: parse without tz and assume UTC
            try:
                created_dt = datetime.fromisoformat(created_str)
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        if (now_utc - created_dt).days <= 7:
            recent_count += 1

    body += f"""

RECENT ORDERS (Last 7 days): {recent_count}
{'-'*40}
Filled: {len([o for o in recent_orders if o.get('status') == 'filled'])}
Cancelled: {len([o for o in recent_orders if o.get('status') == 'canceled'])}
Pending: {len([o for o in recent_orders if o.get('status') in ['new', 'partially_filled', 'pending_new']])}

{'='*60}
AWS AUTOMATED SWING TRADING SYSTEM
Portfolio Report Generated: {datetime.utcnow().isoformat()}
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
            print("Portfolio report email sent successfully")
    except Exception as e:
        print(f"Error sending portfolio report: {e}")

def lambda_handler(event, context):
    """Generate and send portfolio report"""
    print("📊 Portfolio Reporter started")
    
    try:
        # Get account and position data
        account = get_account_info()
        positions = get_positions()
        recent_orders = get_orders(limit=100)
        
        if not account:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to get account information'})
            }
        
        # Send comprehensive report
        send_portfolio_report(account, positions, recent_orders)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Portfolio report sent successfully',
                'portfolio_value': account.get('portfolio_value'),
                'positions_count': len(positions),
                'recent_orders_count': len(recent_orders)
            })
        }
        
    except Exception as e:
        print(f"Error in portfolio reporter: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }