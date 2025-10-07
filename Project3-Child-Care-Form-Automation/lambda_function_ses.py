import json
import boto3

ses = boto3.client('ses')

def lambda_handler(event, context):
    try:
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        name = body.get('name', '')
        date = body.get('date', '')
        
        if not all([name, date]):
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Missing required fields'})
            }
        
        # Create email content
        subject = f"Daily Report - {name} ({date})"
        message = f"""
Daily Child Care Report

Child: {name}
Date: {date}

Report submitted successfully!

This is an automated message from the Child Care Form system.
        """.strip()
        
        # Send email via SES
        ses.send_email(
            Source='mhussain.myindia@gmail.com',
            Destination={'ToAddresses': ['mhussain.myindia@gmail.com']},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': message}}
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Report submitted and email sent!'})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }