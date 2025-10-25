import boto3

REGION='us-east-1'
TABLE='tradebot_signals_table'

symbols = ["RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","KOTAKBANK","LT","MARUTI","TATAMOTORS","HINDUNILVR","ITC","BHARTIARTL","ADANIENT","AXISBANK"]

ddb = boto3.client('dynamodb', region_name=REGION)

keys_to_check = ['MA20','MA50','MA200','RSI14','MACD','MACDSignal','MACDHist','Signal','Confidence','ATR']

results = {}
for sym in symbols:
    try:
        resp = ddb.query(TableName=TABLE, KeyConditionExpression='SymbolKey = :s', ExpressionAttributeValues={':s':{'S': sym}}, ScanIndexForward=False, Limit=1)
        items = resp.get('Items', [])
        if not items:
            results[sym] = {'found': False, 'reason': 'no_items'}
            continue
        it = items[0]
        present = {k: (k in it) for k in keys_to_check}
        results[sym] = {'found': True, 'tradedate': it.get('TradedDate', {}).get('S'), 'present': present}
    except Exception as e:
        results[sym] = {'found': False, 'reason': str(e)}

import json
print(json.dumps(results, indent=2))
