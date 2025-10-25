import json
import boto3
import logging
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from decimal import Decimal
import os
import time

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to fetch historical data and store in DynamoDB
    Enhanced to trigger analysis lambda regardless of success/failure
    """
    
    backfill_success = True
    processed_symbols = []
    # Always use a list for errors so EventBridge detail serializes to an array (not null)
    error_details = []
    failed_symbols = []
    total_symbols = 0
    
    try:
        # Get parameters from event or use defaults
        symbols = event.get('symbols', os.environ.get('SYMBOLS', 'RELIANCE,TCS,INFY').split(','))
        backfill_days = int(event.get('backfilldays', 3))
        total_symbols = len(symbols)
        
        logger.info(f"Starting backfill for symbols: {symbols}, days: {backfill_days}")
        
        # Initialize services
        REGION = os.environ.get('AWS_REGION', 'us-east-1')
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table_name = os.environ.get('DYNAMODB_TABLE', 'tradebot_signals_table')
        table = dynamodb.Table(table_name)
        
        # Get KiteConnect credentials
        try:
            kite = get_kite_instance()
        except Exception as e:
            # Don't abort: record error and continue to attempt to trigger analysis so other lambdas run
            logger.error('Failed to initialize Kite client: %s', e)
            error_details.append(f'KiteInit: {str(e)}')
            kite = None
        
        # Process each symbol
        for symbol in symbols:
            try:
                logger.info(f"Processing symbol: {symbol}")

                # Fetch historical data (if kite client unavailable, record and skip)
                if kite is None:
                    raise Exception('Kite client not available')

                historical_data = fetch_historical_data(kite, symbol, backfill_days)

                if historical_data:
                    # Store in DynamoDB
                    store_data_in_dynamodb(table, symbol, historical_data)
                    processed_symbols.append(symbol)
                    logger.info(f"Successfully processed {symbol}")
                else:
                    logger.error(f"No data received for {symbol}")
                    backfill_success = False
                    failed_symbols.append(symbol)
                    error_details.append(f"{symbol}: no data returned")

            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {str(e)}")
                backfill_success = False
                failed_symbols.append(symbol)
                error_details.append(f"{symbol}: {str(e)}")
        
        # Send notifications (always send a concise summary)
        short_msg = f"Processed {len(processed_symbols)} out of {total_symbols} symbols"
        if backfill_success:
            send_notification("Backfill completed successfully", short_msg)
        else:
            # include short error description in notifications and list failed symbols
            err_short = error_details[0] if error_details else 'See logs'
            failed = ','.join(failed_symbols) if failed_symbols else 'none'
            send_notification("Backfill completed with errors", f"{short_msg}. Failed: {failed}. Error: {err_short}")
        
    except Exception as e:
        logger.error(f"Critical error in lambda_handler: {str(e)}")
        error_details = [f"Critical error: {str(e)}"]
        backfill_success = False
        send_notification("Critical Error", f"Lambda execution failed: {str(e)}")
    finally:
        # ALWAYS publish EventBridge event regardless of success/failure. Put in finally so it runs even on exceptions.
        try:
            event_status = 'success' if backfill_success else 'error'
            event_published = publish_analysis_event(
                context.aws_request_id if hasattr(context, 'aws_request_id') else None,
                event_status,
                processed_symbols,
                total_symbols,
                error_details,
                failed_symbols
            )
            logger.info(f"EventBridge event published: {event_published}")
        except Exception as e:
            logger.error(f"Failed to publish EventBridge event: {str(e)}")
            # Notify about failure to publish event but do not re-raise
            try:
                send_notification('Event publish failed', f'Failed to publish analysis trigger: {str(e)}')
            except Exception:
                logger.exception('Failed sending publish-failure notification')
            event_published = False
    
    # Return response (preserving your original format)
    return {
        'statusCode': 200 if backfill_success else 500,
        'body': json.dumps({
            'message': 'Backfill completed' if backfill_success else 'Backfill failed',
            'symbols_processed': len(processed_symbols),
            'total_symbols': total_symbols,
            'processed_symbols': processed_symbols,
            'analysis_triggered': event_published,
            'error_details': error_details
        })
    }

def get_kite_instance():
    """
    Get KiteConnect instance with credentials from Secrets Manager
    """
    try:
        # Get credentials from Secrets Manager
        secret_name = os.environ.get('SECRET_NAME', 'autotrade-kite/credentials')
        secrets_client = boto3.client('secretsmanager')
        
        response = secrets_client.get_secret_value(SecretId=secret_name)
        credentials = json.loads(response['SecretString'])
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=credentials['api_key'])
        
        # Set access token
        access_token = get_token()
        if access_token:
            kite.set_access_token(access_token)
        else:
            # Use stored access token if available
            if 'access_token' in credentials:
                kite.set_access_token(credentials['access_token'])
            else:
                raise Exception("No access token available")
        
        return kite
        
    except Exception as e:
        logger.error(f"Error initializing KiteConnect: {str(e)}")
        raise e

def get_token():
    """
    TODO: Implement token generation logic
    This should handle the OAuth flow or return stored token
    """
    # Placeholder - implement your token logic here
    return None

def fetch_historical_data(kite, symbol, backfill_days):
    """
    Fetch historical data for a symbol
    """
    try:
        # Calculate date range
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=backfill_days)
        
        logger.info(f"Fetching data for {symbol} from {from_date} to {to_date}")
        
        # Fetch historical data
        historical_data = kite.historical_data(
            instrument_token=get_instrument_token(kite, symbol),
            from_date=from_date,
            to_date=to_date,
            interval="day"
        )
        
        logger.info(f"Fetched {len(historical_data)} records for {symbol}")
        return historical_data
        
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
        return None

def get_instrument_token(kite, symbol):
    """
    Get instrument token for a symbol
    """
    try:
        # Get instruments list
        instruments = kite.instruments("NSE")
        
        # Find the symbol
        for instrument in instruments:
            if instrument['tradingsymbol'] == symbol:
                return instrument['instrument_token']
        
        raise Exception(f"Instrument token not found for {symbol}")
        
    except Exception as e:
        logger.error(f"Error getting instrument token for {symbol}: {str(e)}")
        raise e

def store_data_in_dynamodb(table, symbol, historical_data):
    """
    Store historical data in DynamoDB - PRESERVING YOUR ORIGINAL SCHEMA
    """
    try:
        # Prepare batch write items with YOUR original field names and types
        with table.batch_writer() as batch:
            for record in historical_data:
                item = {
                    'SymbolKey': symbol,  # Your original field name
                    'TradedDate': record['date'].strftime('%Y-%m-%d'),  # Your original field name
                    'Open': Decimal(str(record.get('open', 0))),  # Your original Decimal format
                    'High': Decimal(str(record.get('high', 0))),  # Your original Decimal format
                    'Low': Decimal(str(record.get('low', 0))),  # Your original Decimal format
                    'Close': Decimal(str(record.get('close', 0))),  # Your original Decimal format
                    'Volume': Decimal(str(record.get('volume', 0))),  # Your original Decimal format
                    'Timestamp': datetime.utcnow().isoformat(),  # Your original field name
                    'data_type': 'historical'  # Your original field name
                }
                batch.put_item(Item=item)
        
        logger.info(f"Stored {len(historical_data)} records for {symbol} in DynamoDB")
        
    except Exception as e:
        logger.error(f"Error storing data in DynamoDB for {symbol}: {str(e)}")
        raise e

def send_notification(subject, message):
    """
    Send notification via Telegram and Email
    """
    try:
        # Send Telegram notification
        send_telegram_notification(message)
        
        # Send email notification
        send_email_notification(subject, message)
        
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")

def send_telegram_notification(message):
    """
    Send notification via Telegram
    """
    try:
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            logger.warning("Telegram credentials not configured")
            return
        
        import requests
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': f"🤖 Tradebot Fetch Lambda\n\n{message}",
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            logger.info("Telegram notification sent successfully")
        else:
            logger.error(f"Failed to send Telegram notification: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {str(e)}")

def send_email_notification(subject, message):
    """
    Send notification via SES
    """
    try:
        ses_from = os.environ.get('SES_FROM')
        ses_to = os.environ.get('SES_TO')
        
        if not ses_from or not ses_to:
            logger.warning("SES credentials not configured")
            return
        
        ses_client = boto3.client('ses')
        
        response = ses_client.send_email(
            Source=ses_from,
            Destination={'ToAddresses': [ses_to]},
            Message={
                'Subject': {'Data': f"Tradebot: {subject}"},
                'Body': {
                    'Text': {'Data': message},
                    'Html': {'Data': f"<p>{message}</p>"}
                }
            }
        )
        
        logger.info("Email notification sent successfully")
        
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")

def publish_analysis_event(request_id, status, processed_symbols, total_symbols, error_details=None, failed_symbols=None):
    """
    Publish EventBridge event to trigger analysis lambda
    ALWAYS publishes event regardless of fetch success/failure
    """
    
    # Robust publish with retries and optional Lambda invoke fallback
    REGION = os.environ.get('AWS_REGION', 'us-east-1')
    bus = os.environ.get('EVENT_BUS_NAME')
    eventbridge = boto3.client('events', region_name=REGION)

    event_detail = {
        'fetch_request_id': request_id,
        'timestamp': datetime.utcnow().isoformat(),
        'status': status,  # 'success' or 'error'
        'processed_symbols': processed_symbols,
        'total_symbols': total_symbols,
        'symbols_processed_count': len(processed_symbols),
        'failed_symbols': failed_symbols or [],
        'error_details': error_details,
        'trigger_analysis': True  # Always trigger analysis
    }

    entry = {
        'Source': 'tradebot.fetch',
        'DetailType': 'Fetch Completed',
        'Detail': json.dumps(event_detail, default=str)
    }
    # Only set EventBusName if explicitly configured and not 'default'
    if bus and bus.lower() != 'default':
        entry['EventBusName'] = bus

    payload = [entry]

    # Attempt with retries
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f'Publishing EventBridge event attempt {attempt}/{max_attempts}')
            response = eventbridge.put_events(Entries=payload)
            logger.info('EventBridge response: %s', response)
            if response.get('FailedEntryCount', 1) == 0:
                logger.info('Analysis trigger event published successfully')
                return True
            else:
                logger.error('Event publishing reported failures: %s', response)
        except Exception as e:
            logger.exception('Exception publishing EventBridge event (attempt %s): %s', attempt, e)

        # backoff before retry
        sleep_sec = 2 ** attempt
        logger.info('Sleeping %s seconds before retry', sleep_sec)
        time.sleep(sleep_sec)

    # If we reach here, EventBridge publishing failed repeatedly — try fallback minimal publish
    try:
        logger.info('Attempting fallback EventBridge event after retries')
        fallback_detail = {
            'fetch_request_id': request_id,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'fallback',
            'trigger_analysis': True,
            'fallback_reason': 'put_events retries failed'
        }
        fallback_entry = {
            'Source': 'tradebot.fetch',
            'DetailType': 'Fetch Completed',
            'Detail': json.dumps(fallback_detail, default=str)
        }
        if bus and bus.lower() != 'default':
            fallback_entry['EventBusName'] = bus
        resp = eventbridge.put_events(Entries=[fallback_entry])
        logger.info('Fallback event response: %s', resp)
        if resp.get('FailedEntryCount', 1) == 0:
            return True
    except Exception as e:
        logger.exception('Fallback put_events failed: %s', e)

    # As a last resort, attempt to invoke analysis Lambda directly (async) so downstream still runs
    analysis_fn = os.environ.get('ANALYSIS_LAMBDA_NAME')
    if analysis_fn:
        try:
            logger.info('Invoking analysis Lambda directly as fallback: %s', analysis_fn)
            lambda_client = boto3.client('lambda', region_name=REGION)
            invoke_payload = json.dumps(event_detail, default=str)
            lambda_client.invoke(FunctionName=analysis_fn, InvocationType='Event', Payload=invoke_payload)
            logger.info('Direct Lambda invoke attempted')
            return True
        except Exception as e:
            logger.exception('Direct Lambda invoke fallback failed: %s', e)

    return False
