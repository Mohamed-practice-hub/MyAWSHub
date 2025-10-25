import os
import json
import logging
import boto3
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# This lambda will check the Secrets Manager secret that stores Kite credentials.
# If access_token is missing or appears expired, it will send a Telegram reminder.

def notify_telegram(message):
    try:
        import requests
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if not token or not chat_id:
            logger.warning('TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set, skipping Telegram notification.')
            return
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        requests.post(url, data={'chat_id': chat_id, 'text': message})
    except Exception as e:
        logger.error('Telegram notify failed: %s', e)


def lambda_handler(event, context):
    secret_name = os.environ.get('SECRET_NAME', 'autotrade-kite/credentials')
    sm = boto3.client('secretsmanager')
    try:
        resp = sm.get_secret_value(SecretId=secret_name)
        secret = json.loads(resp.get('SecretString') or '{}')
    except Exception as e:
        logger.error('Failed to read secret %s: %s', secret_name, e)
        notify_telegram(f'Unable to read Kite credentials secret {secret_name}: {e}')
        return {'status': 'error', 'reason': str(e)}

    # Basic checks
    access_token = secret.get('access_token')
    token_ts = secret.get('access_token_ts')  # optional stored timestamp
    expire_hours = int(os.environ.get('TOKEN_EXPIRE_HOURS', '24'))

    needs_refresh = False
    if not access_token:
        needs_refresh = True
        reason = 'access_token missing'
    else:
        if token_ts:
            try:
                ts = datetime.fromisoformat(token_ts)
                if datetime.utcnow() - ts > timedelta(hours=expire_hours):
                    needs_refresh = True
                    reason = 'access_token appears expired based on stored timestamp'
            except Exception:
                # can't parse timestamp; just warn
                logger.warning('Could not parse access_token_ts in secret')

    if needs_refresh:
        msg = f'Kite access token missing/expired: {reason}. Please refresh the token and update Secrets Manager ({secret_name}).'
        notify_telegram(msg)
        return {'status': 'needs_refresh', 'reason': reason}

    logger.info('Kite access_token present; no action required')
    return {'status': 'ok'}
