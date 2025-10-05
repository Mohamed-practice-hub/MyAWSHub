import json
import boto3
import uuid
import os
from datetime import datetime

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')
table_name = os.environ.get('TABLE_NAME', 'project2-ContactSubmissions')
table = dynamodb.Table(table_name)

# Configuration
SENDER_EMAIL = "mhussain.myindia@gmail.com"  # Must be verified in SES
ADMIN_EMAIL = "mhussain.myindia@gmail.com"  # Your admin email

def lambda_handler(event, context):
    # Force logging to work
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    print(f"Received event: {json.dumps(event)}")
    logger.info(f"Received event: {json.dumps(event)}")
    print(f"Using table: {table_name}")
    logger.info(f"Using table: {table_name}")
    
    try:
        # Parse the request body
        if 'body' in event:
            print(f"Raw body: {event['body']}")
            print(f"Raw body type: {type(event['body'])}")
            logger.info(f"Raw body: {event['body']}")
            try:
                body = json.loads(event['body'])
                print(f"JSON parsing successful")
            except Exception as parse_error:
                print(f"JSON parsing failed: {str(parse_error)}")
                body = {}
        else:
            print("No 'body' key in event, using event directly")
            body = event
        
        print(f"Parsed body: {json.dumps(body)}")
        print(f"Parsed body keys: {list(body.keys())}")
        logger.info(f"Parsed body: {json.dumps(body)}")
        
        # Extract form data
        name = body.get('name', '')
        email = body.get('email', '')
        subject = body.get('subject', '')
        message = body.get('message', '')
        
        print(f"Raw values from body.get():")
        print(f"  name: {repr(body.get('name', 'KEY_NOT_FOUND'))}")
        print(f"  email: {repr(body.get('email', 'KEY_NOT_FOUND'))}")
        print(f"  message: {repr(body.get('message', 'KEY_NOT_FOUND'))}")
        print(f"  subject: {repr(body.get('subject', 'KEY_NOT_FOUND'))}")
        
        print(f"Extracted data - Name: {name}, Email: {email}, Subject: {subject}, Message: {message}")
        logger.info(f"Extracted data - Name: {name}, Email: {email}, Subject: {subject}, Message: {message}")
        
        # Debug field values
        print(f"DEBUG - name: '{name}' (length: {len(name)})")
        print(f"DEBUG - email: '{email}' (length: {len(email)})")
        print(f"DEBUG - message: '{message}' (length: {len(message)})")
        
        # Validate required fields
        missing_fields = []
        if not name or name.strip() == '':
            missing_fields.append('name')
            print(f"DEBUG - name is missing or empty")
        if not email or email.strip() == '':
            missing_fields.append('email')
            print(f"DEBUG - email is missing or empty")
        if not message or message.strip() == '':
            missing_fields.append('message')
            print(f"DEBUG - message is missing or empty")
        
        print(f"DEBUG - missing_fields list: {missing_fields}")
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print(f"Validation failed - {error_msg}")
            logger.error(f"Validation failed - {error_msg}")
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'error': error_msg
                })
            }
        
        # Create unique ID and timestamp
        submission_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        print(f"Generated ID: {submission_id}, Timestamp: {timestamp}")
        logger.info(f"Generated ID: {submission_id}, Timestamp: {timestamp}")
        
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
        
        # Add status field to item
        item['status'] = 'new'
        
        # Store in DynamoDB
        response = table.put_item(Item=item)
        print(f"DynamoDB response: {json.dumps(response)}")
        
        # Send email notifications
        try:
            print(f"Starting email notifications...")
            print(f"Sender email: {SENDER_EMAIL}")
            print(f"Admin email: {ADMIN_EMAIL}")
            print(f"User email: {email}")
            
            # Email to admin
            admin_subject = f"New Contact Form Submission: {subject or 'No Subject'}"
            admin_body = f"""
New contact form submission received:

Name: {name}
Email: {email}
Subject: {subject or 'No Subject'}
Message: {message}

Submission ID: {submission_id}
Timestamp: {timestamp}
"""
            
            print(f"Sending admin email with subject: {admin_subject}")
            admin_response = ses.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [ADMIN_EMAIL]},
                Message={
                    'Subject': {'Data': admin_subject},
                    'Body': {'Text': {'Data': admin_body}}
                }
            )
            print(f"Admin email sent successfully. MessageId: {admin_response.get('MessageId')}")
            
            # Confirmation email to user
            user_subject = "Thank you for contacting us!"
            user_body = f"""
Dear {name},

Thank you for reaching out to us. We have received your message and will get back to you soon.

Your message:
Subject: {subject or 'No Subject'}
Message: {message}

Reference ID: {submission_id}

Best regards,
The Team
"""
            
            print(f"Sending user confirmation email to: {email}")
            user_response = ses.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [email]},  # Send to user's email from form
                Message={
                    'Subject': {'Data': user_subject},
                    'Body': {'Text': {'Data': user_body}}
                }
            )
            print(f"User confirmation email sent successfully. MessageId: {user_response.get('MessageId')}")
            print("All email notifications sent successfully")
            
        except Exception as email_error:
            print(f"Email sending error: {str(email_error)}")
            print(f"Email error type: {type(email_error).__name__}")
            import traceback
            print(f"Email error traceback: {traceback.format_exc()}")
            # Continue execution even if email fails
        
        success_response = {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'message': 'Contact form submitted successfully! You will receive a confirmation email shortly.',
                'id': submission_id
            })
        }
        
        print(f"Returning success response: {json.dumps(success_response)}")
        return success_response
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        logger.error(f"Error occurred: {str(e)}")
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
        logger.error(f"Returning error response: {json.dumps(error_response)}")
        return error_response
