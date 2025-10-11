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
TRADING_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}
ses_client = boto3.client('ses')

def get_account_info():
    """Get account information"""
    url = f"{TRADING_URL}/v2/account"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting account info: {e}")
        return None

def get_positions():
    """Get current positions"""
    url = f"{TRADING_URL}/v2/positions"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting positions: {e}")
        return []

def get_orders(status="all", limit=50):
    """Get recent orders"""
    url = f"{TRADING_URL}/v2/orders"
    params = {"status": status, "limit": limit, "direction": "desc"}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting orders: {e}")
        return []

def get_current_price(symbol):
    """Get current price for symbol"""
    url = f"{DATA_URL}/v2/stocks/{symbol}/trades/latest"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        return data.get('trade', {}).get('p', 0)
    except Exception as e:
        print(f"Error getting price for {symbol}: {e}")
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
    
    body += f"""

RECENT ORDERS (Last 7 days): {len([o for o in recent_orders if (datetime.utcnow() - datetime.fromisoformat(o.get('created_at', '2020-01-01T00:00:00').replace('Z', '+00:00'))).days <= 7])}
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
        ses_client.send_email(
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