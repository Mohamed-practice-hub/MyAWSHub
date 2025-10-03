import json
import boto3
import uuid
from datetime import datetime

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')
table = dynamodb.Table('ContactSubmissions')

# Configuration
SENDER_EMAIL = "your-verified-email@example.com"  # Replace with your verified SES email
ADMIN_EMAIL = "admin@example.com"  # Replace with admin email

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
        subject = body.get('subject', 'No Subject')
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
                'timestamp': timestamp,
                'status': 'new'
            }
        )
        
        # Send email notifications
        try:
            # Email to admin
            admin_subject = f"New Contact Form Submission: {subject}"
            admin_body = f"""
            New contact form submission received:
            
            Name: {name}
            Email: {email}
            Subject: {subject}
            Message: {message}
            
            Submission ID: {submission_id}
            Timestamp: {timestamp}
            """
            
            ses.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [ADMIN_EMAIL]},
                Message={
                    'Subject': {'Data': admin_subject},
                    'Body': {'Text': {'Data': admin_body}}
                }
            )
            
            # Confirmation email to user
            user_subject = "Thank you for contacting us!"
            user_body = f"""
            Dear {name},
            
            Thank you for reaching out to us. We have received your message and will get back to you soon.
            
            Your message:
            Subject: {subject}
            Message: {message}
            
            Reference ID: {submission_id}
            
            Best regards,
            The Team
            """
            
            ses.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [email]},
                Message={
                    'Subject': {'Data': user_subject},
                    'Body': {'Text': {'Data': user_body}}
                }
            )
            
        except Exception as email_error:
            print(f"Email sending error: {str(email_error)}")
            # Continue execution even if email fails
        
        return {
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
