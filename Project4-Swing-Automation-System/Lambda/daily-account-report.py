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

def get_today_orders():
    """Get today's orders"""
    url = f"{TRADING_URL}/v2/orders"
    today = datetime.now().strftime('%Y-%m-%d')
    params = {
        "status": "all",
        "limit": 100,
        "after": f"{today}T00:00:00Z",
        "direction": "desc"
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting today's orders: {e}")
        return []

def get_portfolio_history():
    """Get portfolio history for today"""
    url = f"{TRADING_URL}/v2/account/portfolio/history"
    params = {
        "period": "1D",
        "timeframe": "1H"
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting portfolio history: {e}")
        return None

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

def send_daily_account_report(account, positions, today_orders, portfolio_history):
    """Send comprehensive daily account report"""
    
    # Calculate daily performance
    total_value = float(account.get('portfolio_value', 0))
    total_pnl = float(account.get('unrealized_pl', 0))
    day_pnl = 0
    
    if portfolio_history and portfolio_history.get('equity'):
        equity_values = portfolio_history['equity']
        if len(equity_values) >= 2:
            day_pnl = equity_values[-1] - equity_values[0]
    
    # Today's trading activity
    filled_orders = [o for o in today_orders if o.get('status') == 'filled']
    buy_orders = [o for o in filled_orders if o.get('side') == 'buy']
    sell_orders = [o for o in filled_orders if o.get('side') == 'sell']
    
    # Calculate today's trading volume
    total_traded_value = sum(float(o.get('filled_avg_price', 0)) * float(o.get('filled_qty', 0)) for o in filled_orders)
    
    # Performance indicators
    day_pnl_pct = (day_pnl / total_value) * 100 if total_value > 0 else 0
    total_pnl_pct = (total_pnl / total_value) * 100 if total_value > 0 else 0
    
    # Email subject with key metrics
    pnl_emoji = "📈" if day_pnl >= 0 else "📉"
    subject = f"{pnl_emoji} Daily Account Report - ${total_value:,.2f} ({day_pnl:+.2f}) - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
DAILY ACCOUNT REPORT - END OF DAY
{'='*60}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EST
Report Time: 10:00 PM Daily Summary

ACCOUNT OVERVIEW:
{'-'*40}
Portfolio Value: ${total_value:,.2f}
Today's P&L: ${day_pnl:,.2f} ({day_pnl_pct:+.2f}%)
Total Unrealized P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
Buying Power: ${float(account.get('buying_power', 0)):,.2f}
Cash: ${float(account.get('cash', 0)):,.2f}

TODAY'S TRADING ACTIVITY:
{'-'*40}
Total Orders: {len(today_orders)}
Filled Orders: {len(filled_orders)}
Buy Orders: {len(buy_orders)}
Sell Orders: {len(sell_orders)}
Total Traded Value: ${total_traded_value:,.2f}
"""
    
    if filled_orders:
        body += f"\nTODAY'S EXECUTED TRADES:\n{'-'*40}\n"
        for order in filled_orders:
            side_emoji = "🟢" if order['side'] == 'buy' else "🔴"
            filled_price = float(order.get('filled_avg_price', 0))
            filled_qty = float(order.get('filled_qty', 0))
            trade_value = filled_price * filled_qty
            
            body += f"""
{side_emoji} {order['side'].upper()} {order['symbol']}
  Quantity: {filled_qty:,.0f} shares
  Price: ${filled_price:.2f}
  Value: ${trade_value:,.2f}
  Time: {order.get('filled_at', 'N/A')[:19]}
  Order ID: {order.get('id', 'N/A')[:8]}...
"""
    else:
        body += f"\nNo trades executed today.\n"
    
    body += f"\nCURRENT POSITIONS: {len(positions)}\n{'-'*40}\n"
    
    if positions:
        total_market_value = 0
        for pos in positions:
            symbol = pos['symbol']
            qty = float(pos['qty'])
            avg_price = float(pos['avg_entry_price'])
            current_price = get_current_price(symbol)
            market_value = float(pos['market_value'])
            unrealized_pl = float(pos['unrealized_pl'])
            unrealized_pct = float(pos['unrealized_plpc']) * 100
            
            total_market_value += market_value
            position_type = "LONG" if qty > 0 else "SHORT"
            pnl_emoji = "🟢" if unrealized_pl >= 0 else "🔴"
            
            body += f"""
{pnl_emoji} {symbol} ({position_type})
  Shares: {qty:,.0f}
  Entry Price: ${avg_price:.2f}
  Current Price: ${current_price:.2f}
  Market Value: ${market_value:,.2f}
  Unrealized P&L: ${unrealized_pl:,.2f} ({unrealized_pct:+.2f}%)
  Day Change: ${(current_price - avg_price) * qty:,.2f}
"""
        
        body += f"\nTotal Position Value: ${total_market_value:,.2f}\n"
    else:
        body += "No open positions.\n"
    
    # Performance summary
    body += f"""

PERFORMANCE SUMMARY:
{'-'*40}
Starting Value: ${total_value - day_pnl:,.2f}
Ending Value: ${total_value:,.2f}
Day Change: ${day_pnl:,.2f} ({day_pnl_pct:+.2f}%)
Best Performer: {get_best_performer(positions)}
Worst Performer: {get_worst_performer(positions)}

RISK METRICS:
{'-'*40}
Cash Utilization: {((total_value - float(account.get('cash', 0))) / total_value * 100):,.1f}%
Day Trade Count: {account.get('daytrade_count', 0)}/3
Buying Power Used: {((float(account.get('buying_power', 0)) / total_value) * 100):,.1f}%

NEXT TRADING DAY:
{'-'*40}
Market Status: {"Open" if is_market_open() else "Closed"}
Next Analysis: Tomorrow 9:45 AM Toronto time
Scheduled Reports: Weekly performance on Fridays

{'='*60}
AWS AUTOMATED TRADING SYSTEM
Daily Report Generated: {datetime.now().isoformat()}
Account Type: Paper Trading (Risk-Free)
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
        print("Daily account report email sent successfully")
    except Exception as e:
        print(f"Error sending daily account report: {e}")

def get_best_performer(positions):
    """Get best performing position"""
    if not positions:
        return "N/A"
    
    best = max(positions, key=lambda p: float(p.get('unrealized_plpc', 0)))
    pct = float(best.get('unrealized_plpc', 0)) * 100
    return f"{best['symbol']} (+{pct:.2f}%)"

def get_worst_performer(positions):
    """Get worst performing position"""
    if not positions:
        return "N/A"
    
    worst = min(positions, key=lambda p: float(p.get('unrealized_plpc', 0)))
    pct = float(worst.get('unrealized_plpc', 0)) * 100
    return f"{worst['symbol']} ({pct:+.2f}%)"

def is_market_open():
    """Check if market is currently open"""
    url = f"{TRADING_URL}/v2/clock"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        return data.get('is_open', False)
    except:
        return False

def lambda_handler(event, context):
    """Generate and send daily account report"""
    print("📊 Daily Account Reporter started")
    
    try:
        # Get all account data
        account = get_account_info()
        positions = get_positions()
        today_orders = get_today_orders()
        portfolio_history = get_portfolio_history()
        
        if not account:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to get account information'})
            }
        
        # Send comprehensive daily report
        send_daily_account_report(account, positions, today_orders, portfolio_history)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Daily account report sent successfully',
                'portfolio_value': account.get('portfolio_value'),
                'positions_count': len(positions),
                'today_orders_count': len(today_orders)
            })
        }
        
    except Exception as e:
        print(f"Error in daily account reporter: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }