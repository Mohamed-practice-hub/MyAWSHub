import boto3
import json
import os
import time
from datetime import datetime, timedelta, timezone

try:
    import requests
except Exception:
    requests = None

_secrets_client = None
_ses_client = None

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

def _request_with_retries(method: str, url: str, *, headers=None, json_body=None, params=None, timeout=10, max_retries=3, backoff_factor=0.5):
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            if requests is None:
                import urllib.request
                import urllib.parse
                if params:
                    query = urllib.parse.urlencode(params)
                    url2 = f"{url}?{query}"
                else:
                    url2 = url
                req = urllib.request.Request(url2, method=method.upper())
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
                resp = requests.request(method.upper(), url, headers=headers, json=json_body, params=params, timeout=timeout)
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

# Config (lazy secrets)
TRADING_URL = os.environ.get('ALPACA_TRADING_URL', "https://paper-api.alpaca.markets")
DATA_URL = os.environ.get('ALPACA_DATA_URL', "https://data.alpaca.markets")

def get_headers():
    api_key, secret_key = get_alpaca_keys()
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }

def get_account_info():
    """Get account information"""
    url = f"{TRADING_URL}/v2/account"
    try:
        status, data = _request_with_retries('GET', url, headers=get_headers())
        if 200 <= status < 300:
            return data
        return None
    except Exception as e:
        print(f"Error getting account info: {e}")
        return None

def get_positions():
    """Get current positions"""
    url = f"{TRADING_URL}/v2/positions"
    try:
        status, data = _request_with_retries('GET', url, headers=get_headers())
        if 200 <= status < 300:
            return data
        return []
    except Exception as e:
        print(f"Error getting positions: {e}")
        return []

def get_orders(status="all", limit=50):
    """Get recent orders"""
    url = f"{TRADING_URL}/v2/orders"
    params = {"status": status, "limit": limit, "direction": "desc"}
    try:
        status_code, data = _request_with_retries('GET', url, headers=get_headers(), params=params)
        if 200 <= status_code < 300:
            return data
        return []
    except Exception as e:
        print(f"Error getting orders: {e}")
        return []

def get_current_price(symbol):
    """Get current price for symbol"""
    url = f"{DATA_URL}/v2/stocks/{symbol}/trades/latest"
    try:
        status, data = _request_with_retries('GET', url, headers=get_headers())
        if 200 <= status < 300:
            return (data or {}).get('trade', {}).get('p', 0)
        return 0
    except Exception as e:
        print(f"Error getting price for {symbol}: {e}")
        return 0

def send_portfolio_report(account, positions, recent_orders):
    """Send comprehensive portfolio report"""
    
    def _now_utc():
        return datetime.now(timezone.utc)

    def _parse_iso(ts: str):
        if not ts:
            return None
        try:
            # Normalize trailing Z to +00:00 for fromisoformat
            ts2 = ts.replace('Z', '+00:00')
            return datetime.fromisoformat(ts2)
        except Exception:
            return None

    def _ensure_aware(dt):
        if not dt:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    # Calculate totals
    total_value = float(account.get('portfolio_value', 0))
    total_pnl = float(account.get('unrealized_pl', 0))
    buying_power = float(account.get('buying_power', 0))
    
    # Count positions
    long_positions = [p for p in positions if float(p['qty']) > 0]
    short_positions = [p for p in positions if float(p['qty']) < 0]
    
    # Recent trades
    filled_orders = [o for o in recent_orders if o.get('status') == 'filled']
    today_orders = [o for o in filled_orders if o.get('filled_at', '').startswith(_now_utc().strftime('%Y-%m-%d'))]
    
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
    
    body += f"""

RECENT ORDERS (Last 7 days): {sum(1 for o in recent_orders if (lambda _dt: (_dt is not None and (_now_utc() - _dt).days <= 7))(_ensure_aware(_parse_iso(o.get('created_at', '')))))}
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
        get_ses_client().send_email(
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