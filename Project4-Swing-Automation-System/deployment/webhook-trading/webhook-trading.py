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
s3_client = boto3.client('s3')
S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')

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
    print("🔗 Webhook Trading Lambda started")
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
    
    # Execute trade
    trades = []
    
    print(f"Executing {webhook_data['action']} order for {webhook_data['symbol']}")
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