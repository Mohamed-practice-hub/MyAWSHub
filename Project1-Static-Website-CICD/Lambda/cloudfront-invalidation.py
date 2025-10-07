import boto3
import json
import uuid
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to invalidate CloudFront distribution cache
    """
    
    # Your CloudFront distribution ID
    distribution_id = 'E2WPPNQQHU3K9B'
    
    # Initialize CloudFront client
    cloudfront = boto3.client('cloudfront')
    
    try:
        logger.info(f"Starting CloudFront invalidation for distribution: {distribution_id}")
        
        # Create invalidation for all files
        response = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 1,
                    'Items': ['/*']  # Invalidate all files
                },
                'CallerReference': str(uuid.uuid4())  # Unique reference ID
            }
        )
        
        invalidation_id = response['Invalidation']['Id']
        logger.info(f"CloudFront invalidation created successfully: {invalidation_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'CloudFront invalidation created successfully',
                'invalidationId': invalidation_id,
                'distributionId': distribution_id,
                'status': response['Invalidation']['Status']
            })
        }
        
    except Exception as e:
        error_message = f"Error creating CloudFront invalidation: {str(e)}"
        logger.error(error_message)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message,
                'distributionId': distribution_id
            })
        }