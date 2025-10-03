import json
import boto3
import logging
from datetime import datetime
import re
import traceback
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SES client
try:
    ses_client = boto3.client('ses', region_name='us-east-1')
    logger.info("SES client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize SES client: {str(e)}")
    ses_client = None

def lambda_handler(event, context):
    """
    Handle contact form submissions with comprehensive error handling
    """
    
    # CRITICAL DEBUG - Log raw event first
    logger.error(f"CRITICAL DEBUG - Raw event: {event}")
    logger.error(f"CRITICAL DEBUG - Event type: {type(event)}")
    logger.error(f"CRITICAL DEBUG - httpMethod value: {event.get('httpMethod', 'NOT_FOUND')}")
    
    # Log the entire event for debugging
    logger.info(f"Full event structure: {json.dumps(event, indent=2, default=str)}")
    logger.info(f"Event keys: {list(event.keys())}")
    
    # Check if this is a proxy integration
    is_proxy = 'httpMethod' in event and 'headers' in event
    logger.info(f"Is Lambda Proxy Integration: {is_proxy}")
    
    # Check event type and extract HTTP method
    http_method = None
    logger.error(f"CRITICAL DEBUG - Checking for httpMethod in event keys: {list(event.keys())}")
    
    if 'httpMethod' in event:
        # API Gateway REST API
        http_method = event['httpMethod']
        logger.error(f"CRITICAL DEBUG - Found httpMethod: {http_method}")
        logger.info("Event type: API Gateway REST API")
    elif 'requestContext' in event and 'http' in event['requestContext']:
        # API Gateway HTTP API or Lambda Function URL
        http_method = event['requestContext']['http']['method']
        logger.error(f"CRITICAL DEBUG - Found HTTP method in requestContext: {http_method}")
        logger.info("Event type: API Gateway HTTP API or Lambda Function URL")
    else:
        logger.error("CRITICAL DEBUG - NO httpMethod found anywhere!")
        logger.error(f"CRITICAL DEBUG - Full event dump: {json.dumps(event, default=str)}")
        logger.warning("Unknown event type - no httpMethod found")
        logger.info(f"Event keys: {list(event.keys())}")
        http_method = 'UNKNOWN'
    
    # CORS and Security headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Content-Type': 'application/json',
        # Security headers
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }
    
    try:
        # Handle preflight OPTIONS request
        if http_method == 'OPTIONS':
            logger.info("Handling OPTIONS preflight request")
            if is_proxy:
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({'message': 'CORS preflight successful'})
                }
            else:
                return {'message': 'CORS preflight successful'}
        
        logger.info(f"HTTP Method: {http_method}")
        
        if http_method != 'POST':
            logger.warning(f"Invalid HTTP method: {http_method}")
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Method {http_method} not allowed. Use POST.',
                    'debug': {
                        'httpMethod': http_method,
                        'allowedMethods': ['POST', 'OPTIONS']
                    }
                })
            }
        
        # Parse request body
        raw_body = event.get('body')
        logger.info(f"Raw body type: {type(raw_body)}")
        logger.info(f"Raw body content: {raw_body}")
        logger.info(f"Is base64 encoded: {event.get('isBase64Encoded', False)}")
        
        if not raw_body:
            logger.error("No body found in request")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Request body is empty',
                    'debug': {
                        'event_keys': list(event.keys()),
                        'body': raw_body,
                        'isBase64Encoded': event.get('isBase64Encoded', False)
                    }
                })
            }
        
        try:
            if event.get('isBase64Encoded', False):
                import base64
                logger.info("Decoding base64 body")
                decoded_body = base64.b64decode(raw_body).decode('utf-8')
                logger.info(f"Decoded body: {decoded_body}")
                form_data = json.loads(decoded_body)
            else:
                logger.info("Parsing JSON body directly")
                form_data = json.loads(raw_body)
            
            logger.info(f"Parsed form data: {form_data}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Invalid JSON format in request body',
                    'debug': {
                        'json_error': str(e),
                        'raw_body': raw_body[:500],
                        'body_type': type(raw_body).__name__
                    }
                })
            }
        
        # Extract form fields
        name = form_data.get('name', '').strip() if form_data.get('name') else ''
        email = form_data.get('email', '').strip() if form_data.get('email') else ''
        subject = form_data.get('subject', '').strip() if form_data.get('subject') else ''
        message = form_data.get('message', '').strip() if form_data.get('message') else ''
        
        logger.info(f"Extracted fields - Name: '{name}', Email: '{email}', Subject: '{subject}', Message length: {len(message)}")
        
        # Validate required fields
        missing_fields = []
        if not name:
            missing_fields.append('name')
        if not email:
            missing_fields.append('email')
        if not message:
            missing_fields.append('message')
        
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Missing required fields: {", ".join(missing_fields)}',
                    'debug': {
                        'missing_fields': missing_fields,
                        'received_fields': list(form_data.keys()),
                        'field_values': {
                            'name': name,
                            'email': email,
                            'subject': subject,
                            'message_length': len(message)
                        }
                    }
                })
            }
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            logger.warning(f"Invalid email format: {email}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Invalid email format',
                    'debug': {
                        'provided_email': email,
                        'email_pattern': email_pattern
                    }
                })
            }
        
        # Send email via SES
        sender_email = os.environ.get('SENDER_EMAIL', 'mhussain.myindia@gmail.com')
        recipient_email = os.environ.get('RECIPIENT_EMAIL', 'mhussain.myindia@gmail.com')
        
        email_subject = f"Portfolio Contact: {subject}" if subject else f"Portfolio Contact from {name}"
        email_body = f"""
New contact form submission:

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}

Submitted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """
        
        response = ses_client.send_email(
            Source=sender_email,
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Subject': {'Data': email_subject, 'Charset': 'UTF-8'},
                'Body': {'Text': {'Data': email_body, 'Charset': 'UTF-8'}}
            }
        )
        
        logger.info(f"Email sent successfully. MessageId: {response['MessageId']}")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': 'Thank you for your message! I will get back to you soon.',
                'debug': {
                    'messageId': response['MessageId'],
                    'timestamp': datetime.now().isoformat(),
                    'sender': sender_email,
                    'recipient': recipient_email
                }
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'debug': {
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'event_summary': {
                        'httpMethod': event.get('httpMethod'),
                        'has_body': 'body' in event,
                        'body_type': type(event.get('body')).__name__ if 'body' in event else 'None',
                        'isBase64Encoded': event.get('isBase64Encoded', False)
                    }
                }
            })
        }