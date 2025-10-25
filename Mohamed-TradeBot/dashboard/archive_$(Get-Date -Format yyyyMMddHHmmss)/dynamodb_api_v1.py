import json
import boto3
import os

dynamodb = boto3.client('dynamodb')
TABLE_NAME = os.environ.get('DDB_TABLE', 'tradebot_table')

def convert(attr):
    # Convert DynamoDB JSON types to plain Python values
    if 'S' in attr: return attr['S']
    if 'N' in attr: return int(attr['N']) if '.' not in attr['N'] else float(attr['N'])
    if 'BOOL' in attr: return attr['BOOL']
    if 'M' in attr: return {k: convert(v) for k,v in attr['M'].items()}
    if 'L' in attr: return [convert(v) for v in attr['L']]
    return None


def lambda_handler(event, context):
    # Simple scan with pagination (for small tables). Consider using queries or DDB streams for large tables.
    items = []
    kwargs = {'TableName': TABLE_NAME}
    try:
        while True:
            resp = dynamodb.scan(**kwargs)
            for i in resp.get('Items', []):
                items.append({k: convert(v) for k,v in i.items()})
            if 'LastEvaluatedKey' in resp:
                kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            else:
                break
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(items)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
