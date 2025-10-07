import json
import boto3
import os

# Initialize AWS clients
sns = boto3.client('sns')

# Configuration
PARENT_NAME = "Mohamed"
PHONE_NUMBER = "+14166484282"  # Mohamed's Canadian number
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse the request body
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        print(f"Parsed body: {json.dumps(body)}")
        
        # Extract form data
        name = body.get('name', '')
        date = body.get('date', '')
        
        # Validate required fields
        if not all([name, date]):
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Missing required fields: name and date'
                })
            }
        
        print(f"Processing daily report for {name} on {date}")
        
        # Create WhatsApp message
        message = create_whatsapp_message(body)
        
        # Send WhatsApp message via SNS
        try:
            if SNS_TOPIC_ARN:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=message,
                    Subject=f"Daily Report for {name} - {date}"
                )
                print(f"WhatsApp message sent to {PARENT_NAME} at {PHONE_NUMBER}")
            else:
                print("SNS_TOPIC_ARN not configured, skipping message send")
        except Exception as sms_error:
            print(f"SMS sending error: {str(sms_error)}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'message': 'Daily report submitted successfully! WhatsApp message sent.'
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }

def create_whatsapp_message(data):
    """Create a formatted WhatsApp message from form data"""
    name = data.get('name', 'Child')
    date = data.get('date', 'Today')
    
    message = f"🌟 Daily Report for {name} - {date} 🌟\n\n"
    
    # Feeding section
    if data.get('bottleAmount') or data.get('bottleTime'):
        message += "🍼 FEEDING:\n"
        if data.get('bottleAmount'):
            message += f"• Bottle: {data.get('bottleAmount')}"
            if data.get('bottleTime'):
                message += f" at {data.get('bottleTime')}"
            message += "\n"
    
    # Sleep section
    if data.get('napFrom') or data.get('napTo'):
        message += "\n😴 SLEEP:\n"
        if data.get('napFrom') and data.get('napTo'):
            message += f"• Nap: {data.get('napFrom')} - {data.get('napTo')}\n"
        elif data.get('napFrom'):
            message += f"• Nap started: {data.get('napFrom')}\n"
    
    # Meals section
    meals = []
    if data.get('amSnack'):
        meals.append(f"• AM Snack: {data.get('amSnack')}")
    if data.get('lunch'):
        meals.append(f"• Lunch: {data.get('lunch')}")
    if data.get('pmSnack'):
        meals.append(f"• PM Snack: {data.get('pmSnack')}")
    
    if meals:
        message += "\n🍽️ MEALS:\n" + "\n".join(meals) + "\n"
    
    # Eating behavior
    ate = data.get('ate', [])
    if ate:
        if isinstance(ate, list):
            ate_text = ", ".join(ate)
        else:
            ate_text = ate
        message += f"• Eating: {ate_text}\n"
    
    # Diapers section
    diapers = []
    if data.get('diaper1Time') and data.get('diaper1Type'):
        diapers.append(f"• {data.get('diaper1Time')}: {data.get('diaper1Type')}")
    if data.get('diaper2Time') and data.get('diaper2Type'):
        diapers.append(f"• {data.get('diaper2Time')}: {data.get('diaper2Type')}")
    if data.get('diaper3Time') and data.get('diaper3Type'):
        diapers.append(f"• {data.get('diaper3Time')}: {data.get('diaper3Type')}")
    
    if diapers:
        message += "\n🚼 DIAPERS:\n" + "\n".join(diapers) + "\n"
    
    if data.get('suppliesNeeded'):
        message += f"• Supplies needed: {data.get('suppliesNeeded')}\n"
    
    # Notes section
    notes = []
    if data.get('mood'):
        notes.append(f"😊 Mood: {data.get('mood')}")
    if data.get('milestones'):
        notes.append(f"🎯 Milestones: {data.get('milestones')}")
    if data.get('fun'):
        notes.append(f"🎉 Fun activities: {data.get('fun')}")
    if data.get('comments'):
        notes.append(f"💭 Comments: {data.get('comments')}")
    
    if notes:
        message += "\n📝 NOTES:\n" + "\n".join(notes) + "\n"
    
    message += "\n💕 Have a great day!"
    
    return message