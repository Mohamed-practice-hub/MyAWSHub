import boto3, json, sys

client = boto3.client('lambda', region_name='us-east-1')

functions = [
    ('tradebot_fetch_lambda','test from assistant - fetch'),
    ('tradebot-analysis-lambda','test from assistant - analysis'),
    ('tradebot-dynamo-stream-exporter','test from assistant - exporter')
]

for fn, msg in functions:
    payload = {"test_notification": True, "test_message": msg}
    print('\nInvoking', fn)
    try:
        r = client.invoke(FunctionName=fn, Payload=json.dumps(payload))
        status = r.get('StatusCode')
        body = r['Payload'].read().decode('utf-8')
        print('StatusCode:', status)
        print('ResponsePayload:', body)
    except Exception as e:
        print('Invoke failed for', fn, e)
        sys.exit(1)

print('\nDone')
