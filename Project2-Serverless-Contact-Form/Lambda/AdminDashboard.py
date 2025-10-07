import json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ContactSubmissions')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    try:
        http_method = event.get('httpMethod', '')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        if http_method == 'GET':
            if 'id' in path_parameters:
                # Get specific submission
                response = table.get_item(Key={'id': path_parameters['id']})
                if 'Item' in response:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Origin': '*',
                            'Content-Type': 'application/json'
                        },
                        'body': json.dumps(response['Item'], cls=DecimalEncoder)
                    }
                else:
                    return {
                        'statusCode': 404,
                        'headers': {'Access-Control-Allow-Origin': '*'},
                        'body': json.dumps({'error': 'Submission not found'})
                    }
            else:
                # Get all submissions with pagination
                limit = int(query_parameters.get('limit', 50))
                last_key = query_parameters.get('lastKey')
                
                scan_kwargs = {'Limit': limit}
                if last_key:
                    scan_kwargs['ExclusiveStartKey'] = {'id': last_key}
                
                response = table.scan(**scan_kwargs)
                
                # Sort by timestamp (newest first)
                items = sorted(response['Items'], 
                             key=lambda x: x.get('timestamp', ''), 
                             reverse=True)
                
                result = {
                    'submissions': items,
                    'count': len(items)
                }
                
                if 'LastEvaluatedKey' in response:
                    result['lastKey'] = response['LastEvaluatedKey']['id']
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps(result, cls=DecimalEncoder)
                }
        
        elif http_method == 'PUT':
            # Update submission status
            submission_id = path_parameters.get('id')
            body = json.loads(event.get('body', '{}'))
            status = body.get('status', 'new')
            
            table.update_item(
                Key={'id': submission_id},
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': status}
            )
            
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Status updated successfully'})
            }
        
        elif http_method == 'DELETE':
            # Delete submission
            submission_id = path_parameters.get('id')
            table.delete_item(Key={'id': submission_id})
            
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Submission deleted successfully'})
            }
        
        else:
            return {
                'statusCode': 405,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error'})
        }
