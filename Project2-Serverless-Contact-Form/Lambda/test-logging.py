import json
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    print("PRINT: This is a print statement")
    logger.info("LOGGER: This is a logger statement")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Logging test complete')
    }