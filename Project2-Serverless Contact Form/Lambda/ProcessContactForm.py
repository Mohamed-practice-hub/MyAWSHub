import json
import boto3
import uuid
import os
from datetime import datetime

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME', 'ContactSubmissions')
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    print(f"Using table: {table_name}")
    
    try:
        # Parse the request body
        if 'body' in event:
            print(f"Raw body: {event['body']}")
            body = json.loads(event['body'])
        else:
            body = event
        
        print(f"Parsed body: {json.dumps(body)}")
        
        # Extract form data
        name = body.get('name', '')
        email = body.get('email', '')
        subject = body.get('subject', '')
        message = body.get('message', '')
        
        print(f"Extracted data - Name: {name}, Email: {email}, Subject: {subject}, Message: {message}")
        
        # Validate required fields
        if not all([name, email, message]):
            print("Validation failed - missing required fields")
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
        
        print(f"Generated ID: {submission_id}, Timestamp: {timestamp}")
        
        # Prepare item for DynamoDB
        item = {
            'id': submission_id,
            'name': name,
            'email': email,
            'subject': subject,
            'message': message,
            'timestamp': timestamp
        }
        
        print(f"Inserting item: {json.dumps(item)}")
        
        # Store in DynamoDB
        response = table.put_item(Item=item)
        print(f"DynamoDB response: {json.dumps(response)}")
        
        success_response = {
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
        
        print(f"Returning success response: {json.dumps(success_response)}")
        return success_response
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        error_response = {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        }
        
        print(f"Returning error response: {json.dumps(error_response)}")
        return error_response
