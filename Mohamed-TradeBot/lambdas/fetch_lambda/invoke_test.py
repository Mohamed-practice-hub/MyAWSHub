import boto3, json
client = boto3.client('lambda', region_name='us-east-1')
payload = {"symbols":["RELIANCE"], "backfilldays":1}
resp = client.invoke(FunctionName='tradebot_fetch_lambda', Payload=json.dumps(payload))
print(resp.get('StatusCode'))
print(resp.get('Payload').read().decode())
