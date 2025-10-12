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

# Initialize
API_KEY, SECRET_KEY = get_alpaca_keys()
TRADING_URL = "https://paper-api.alpaca.markets"
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}
ses_client = boto3.client('ses')

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
        return {"error": str(e)}

def send_test_email(test_results):
    """Send test results email"""
    subject = f"🧪 TRADING TEST RESULTS - {len([r for r in test_results if r.get('success')])} SUCCESS - {datetime.utcnow().strftime('%Y-%m-%d')}"
    
    body = f"""
TRADING SYSTEM TEST RESULTS
{'='*60}
Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Test Type: FORCED BUY/SELL ORDERS

TEST SUMMARY:
{'-'*40}
Total Tests: {len(test_results)}
Successful: {len([r for r in test_results if r.get('success')])}
Failed: {len([r for r in test_results if not r.get('success')])}

DETAILED RESULTS:
{'-'*40}
"""
    
    for test in test_results:
        status = "✅ SUCCESS" if test.get('success') else "❌ FAILED"
        body += f"""
{status} {test['action']} {test['symbol']}
  Order ID: {test.get('order_id', 'N/A')}
  Status: {test.get('order_status', 'N/A')}
  Quantity: {test.get('qty', 1)} shares
  Error: {test.get('error', 'None')}
"""
    
    body += f"""

NEXT STEPS:
{'-'*40}
1. Check Alpaca paper trading account for executed orders
2. Run portfolio reporter to see positions
3. Verify orders in Alpaca dashboard

{'='*60}
AWS TRADING SYSTEM TEST
Test Execution: {datetime.utcnow().isoformat()}
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
        print("Test results email sent successfully")
    except Exception as e:
        print(f"Error sending test email: {e}")

def lambda_handler(event, context):
    """Test trading functionality with forced orders"""
    print("🧪 Trading Test Lambda started")
    
    # Test configuration
    test_mode = event.get('test_mode', 'both')  # 'buy', 'sell', or 'both'
    test_symbol = event.get('symbol', 'AAPL')
    
    test_results = []
    
    if test_mode in ['buy', 'both']:
        print(f"Testing BUY order for {test_symbol}")
        buy_result = place_order(test_symbol, "buy", qty=1)
        
        test_results.append({
            'action': 'BUY',
            'symbol': test_symbol,
            'success': 'id' in buy_result,
            'order_id': buy_result.get('id', 'N/A'),
            'order_status': buy_result.get('status', 'N/A'),
            'qty': 1,
            'error': buy_result.get('error', None)
        })
    
    if test_mode in ['sell', 'both']:
        print(f"Testing SELL order for {test_symbol}")
        sell_result = place_order(test_symbol, "sell", qty=1)
        
        test_results.append({
            'action': 'SELL',
            'symbol': test_symbol,
            'success': 'id' in sell_result,
            'order_id': sell_result.get('id', 'N/A'),
            'order_status': sell_result.get('status', 'N/A'),
            'qty': 1,
            'error': sell_result.get('error', None)
        })
    
    # Send test results email
    send_test_email(test_results)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Trading test completed - {len(test_results)} orders tested',
            'test_results': test_results
        })
    }