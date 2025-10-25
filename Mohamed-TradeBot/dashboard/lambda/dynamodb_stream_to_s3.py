import json
import boto3
import os
import logging
from botocore.exceptions import ClientError
import tempfile
import csv
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

# Environment variables
TABLE_NAME = os.environ.get('DDB_TABLE', 'tradebot_table')
S3_BUCKET = os.environ.get('S3_BUCKET', '')
S3_KEY = os.environ.get('S3_KEY', 'data.json')
CONSISTENT_READ = os.environ.get('CONSISTENT_READ', 'false').lower() == 'true'

# DynamoDB resource/table (initialized after TABLE_NAME is known)
dynamodb_resource = boto3.resource('dynamodb')
table_resource = dynamodb_resource.Table(TABLE_NAME)


# Notification helpers (Telegram + SES)
def notify_telegram(message):
    try:
        # Prefer requests but fall back to urllib to avoid a hard dependency on requests in the Lambda env
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if not token or not chat_id:
            logger.warning('TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set, skipping Telegram notification.')
            return
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        logger.info(f'Sending Telegram notification: {message}')
        try:
            import requests
            requests.post(url, data={'chat_id': chat_id, 'text': message}, timeout=5)
        except Exception:
            # fallback using urllib.request to avoid requiring requests
            try:
                from urllib import parse, request
                data = parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
                req = request.Request(url, data=data)
                request.urlopen(req, timeout=5)
            except Exception as e:
                logger.error(f'Telegram notify failed (urllib fallback): {e}')
    except Exception as e:
        logger.error(f'Telegram notify failed: {e}')


def notify_email(subject, body):
    try:
        ses = boto3.client('ses')
        sender = os.environ.get('SES_FROM')
        recipient = os.environ.get('SES_TO')
        if not sender or not recipient:
            logger.warning('SES_FROM or SES_TO not set, skipping email notification')
            return
        logger.info(f'Sending SES email: subject={subject}')
        ses.send_email(
            Source=sender,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
    except Exception as e:
        logger.error(f'SES notify failed: {e}')


def convert_ddb_item(item):
    # Convert DynamoDB JSON to plain Python types using boto3 TypeDeserializer
    from boto3.dynamodb.types import TypeDeserializer
    d = TypeDeserializer()
    return {k: d.deserialize(v) for k, v in item.items()}


def scan_table(table_name):
    # Return a paginator iterator; caller can set ConsistentRead via paginate params
    paginator = dynamodb.get_paginator('scan')
    if CONSISTENT_READ:
        return paginator.paginate(TableName=table_name, ConsistentRead=True)
    return paginator.paginate(TableName=table_name)


def lambda_handler(event, context):
    logger.info(f"Received stream event with {len(event.get('Records', []))} records")
    # Test mode: if invoked with {"test_notification": true} send a test notification and return
    try:
        if isinstance(event, dict) and event.get('test_notification'):
            msg = event.get('test_message', 'Test notification from tradebot-dynamo-stream-exporter')
            notify_telegram(f"[TEST] {msg}")
            notify_email('Test notification from exporter', msg)
            return {'status': 'test_sent'}
    except Exception:
        logger.exception('Failed running test notification')
    if not S3_BUCKET:
        raise ValueError('S3_BUCKET env var not set')

    try:
        # First try to read a small meta item that records the DB last-modified timestamp.
        # This is written by the fetch lambda as a single put_item and avoids a full table scan.
        db_last_modified = None
        try:
            try:
                meta = dynamodb.get_item(TableName=TABLE_NAME, Key={'SymbolKey': {'S': '__meta__'}, 'TradedDate': {'S': '__config__'}})
                if meta and 'Item' in meta and 'DBLastModified' in meta['Item']:
                    # DBLastModified stored as string attribute
                    db_last_modified = meta['Item']['DBLastModified'].get('S')
                    logger.info(f'Read DBLastModified from meta item: {db_last_modified}')
            except Exception:
                logger.exception('Failed reading meta item from DynamoDB; will fallback to scanning the table')

            # Fallback: compute DB last-modified by scanning the table and finding the max Timestamp value
            if not db_last_modified:
                paginator = dynamodb.get_paginator('scan')
                params = {'TableName': TABLE_NAME, 'ProjectionExpression': 'Timestamp'}
                if CONSISTENT_READ:
                    params['ConsistentRead'] = True
                from boto3.dynamodb.types import TypeDeserializer
                deserializer = TypeDeserializer()
                max_dt = None
                for page in paginator.paginate(**params):
                    for it in page.get('Items', []):
                        try:
                            # deserialize single attribute dict
                            obj = {k: deserializer.deserialize(v) for k, v in it.items()}
                            ts = obj.get('Timestamp')
                            if ts:
                                from datetime import datetime as _dt, timezone as _tz
                                try:
                                    t = _dt.fromisoformat(ts)
                                    if t.tzinfo is None:
                                        t = t.replace(tzinfo=_tz.utc)
                                    if max_dt is None or t > max_dt:
                                        max_dt = t
                                except Exception:
                                    # ignore parse errors for individual items
                                    continue
                        except Exception:
                            continue
                if max_dt:
                    db_last_modified = max_dt.isoformat()
                    logger.info(f'Computed DB last-modified from table: {db_last_modified}')
        except Exception:
            logger.exception('Failed scanning table for Timestamp; proceeding with export')

        # Compare with existing data.json last-modified in S3; if data.json is newer or equal, skip
        try:
            head = s3.head_object(Bucket=S3_BUCKET, Key=S3_KEY)
            data_last_mod = head.get('LastModified')
        except Exception:
            data_last_mod = None
        logger.info(f"DB last-modified (computed): {db_last_modified}")
        logger.info(f"S3 data.json LastModified: {data_last_mod}")

        # If we couldn't compute a DB last-modified timestamp, skip export to avoid unnecessary writes
        if not db_last_modified:
            logger.info('Could not determine DB last-modified timestamp; skipping export to avoid overwriting data.json')
            return {'status': 'skipped', 'reason': 'no db timestamp'}

        if db_last_modified and data_last_mod:
            try:
                from datetime import datetime as _dt, timezone as _tz
                # parse and assume UTC if naive
                db_dt = _dt.fromisoformat(db_last_modified)
                if db_dt.tzinfo is None:
                    db_dt = db_dt.replace(tzinfo=_tz.utc)
                # data_last_mod is timezone-aware
                if data_last_mod >= db_dt:
                    logger.info('data.json is up-to-date; skipping export')
                    return {'status': 'skipped', 'reason': 'data.json up-to-date'}
            except Exception:
                logger.exception('Failed comparing timestamps; proceeding with export')

        # Perform a full scan and stream results to a temp file, then upload
        iterator = scan_table(TABLE_NAME)
        tmp_path = os.path.join(tempfile.gettempdir(), 'data.json')
        count = 0
        first = True
        # Write JSON array streaming to avoid building a large in-memory list
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('[')
            for page in iterator:
                for it in page.get('Items', []):
                    obj = convert_ddb_item(it)
                    if not first:
                        f.write(',')
                    else:
                        first = False
                    json.dump(obj, f, default=str, ensure_ascii=False)
                    count += 1
            f.write(']')

        # Upload file to S3 (upload_file handles multipart when needed)
        s3.upload_file(tmp_path, S3_BUCKET, S3_KEY, ExtraArgs={'ContentType': 'application/json'})
        logger.info(f"Wrote {count} items to s3://{S3_BUCKET}/{S3_KEY}")
        try:
            notify_telegram(f"Exporter: wrote {count} items to s3://{S3_BUCKET}/{S3_KEY}")
        except Exception:
            logger.exception('Failed sending exporter success telegram')

        # Update meta item in DynamoDB to reflect that data.json was regenerated.
        # Use update_item so we don't clobber other meta attributes (like DBLastModified written by fetch lambda).
        try:
            now_iso = datetime.utcnow().isoformat()
            table_resource.update_item(
                Key={'SymbolKey': '__meta__', 'TradedDate': '__config__'},
                UpdateExpression='SET DataJSONLastModified = :v',
                ExpressionAttributeValues={':v': now_iso}
            )
            logger.info(f'Updated meta item in DynamoDB table {TABLE_NAME} with DataJSONLastModified={now_iso}')
        except Exception:
            logger.exception('Failed writing DataJSONLastModified to DynamoDB')

        # --- Server-side CSV generation: read the JSON snapshot and write a CSV to S3
        try:
            tmp_csv_path = os.path.join(tempfile.gettempdir(), 'data.csv')
            with open(tmp_path, 'r', encoding='utf-8') as jf:
                items = json.load(jf)

            # Determine CSV headers (union of all keys)
            header_fields = []
            seen = set()
            for r in items:
                if isinstance(r, dict):
                    for k in r.keys():
                        if k not in seen:
                            seen.add(k)
                            header_fields.append(k)

            # Write CSV to tmp file
            if header_fields:
                with open(tmp_csv_path, 'w', newline='', encoding='utf-8') as cf:
                    writer = csv.DictWriter(cf, fieldnames=header_fields, extrasaction='ignore')
                    writer.writeheader()
                    for r in items:
                        # stringify values
                        row = {k: ('' if r.get(k) is None else str(r.get(k))) for k in header_fields}
                        writer.writerow(row)
            else:
                # no items or no headers, write an empty csv
                open(tmp_csv_path, 'w', encoding='utf-8').close()

            # Upload CSV to S3 (overwrite data.csv)
            csv_key = os.environ.get('CSV_S3_KEY', 'data.csv')
            s3.upload_file(tmp_csv_path, S3_BUCKET, csv_key, ExtraArgs={'ContentType': 'text/csv'})
            logger.info(f"Wrote CSV to s3://{S3_BUCKET}/{csv_key}")
            try:
                notify_telegram(f"Exporter: wrote CSV to s3://{S3_BUCKET}/{csv_key}")
            except Exception:
                logger.exception('Failed sending exporter CSV telegram')
        except Exception:
            logger.exception('Failed generating/uploading CSV snapshot')

        return {'status': 'ok', 'count': count}
    except ClientError as e:
        logger.error(f"AWS error: {e}")
        # notify
        try:
            notify_telegram(f"Exporter Lambda AWS error: {e}")
            notify_email('Exporter Lambda ERROR', str(e))
        except Exception:
            logger.exception('Failed sending error notifications')
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        try:
            notify_telegram(f"Exporter Lambda ERROR: {e}")
            notify_email('Exporter Lambda ERROR', str(e))
        except Exception:
            logger.exception('Failed sending error notifications')
        raise
