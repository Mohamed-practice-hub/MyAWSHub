import json
import boto3
import uuid
from datetime import datetime

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ContactSubmissions')

def lambda_handler(event, context):
    try:
        # Parse the request body
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        # Extract form data
        name = body.get('name', '')
        email = body.get('email', '')
        subject = body.get('subject', '')
        message = body.get('message', '')
        
        # Validate required fields
        if not all([name, email, message]):
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Missing required fields: name, email, and message'
                })
            }
        
        # Create unique ID and timestamp
        submission_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Store in DynamoDB
        table.put_item(
            Item={
                'id': submission_id,
                'name': name,
                'email': email,
                'subject': subject,
                'message': message,
                'timestamp': timestamp
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'message': 'Contact form submitted successfully!',
                'id': submission_id
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }
