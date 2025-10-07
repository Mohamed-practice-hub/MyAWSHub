import json
import boto3

sns = boto3.client('sns')
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:206055866143:project3-childcare-sms'

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
        
        message = f"Daily Report for {name} - {date}\n\nReport submitted successfully!"
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=f"Daily Report - {name}"
        )
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Report submitted and message sent!'})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }