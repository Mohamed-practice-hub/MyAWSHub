import os
import csv
import json
import tempfile
import time
import boto3
import logging
from typing import Any, Dict, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'tradebot_signals_table')
S3_BUCKET = os.environ.get('S3_BUCKET', os.environ.get('S3_BUCKET_NAME', ''))
CSV_PREFIX = os.environ.get('CSV_PREFIX', 'csv_exports')
CONSISTENT_READ = os.environ.get('CONSISTENT_READ', 'false').lower() == 'true'


def convert_ddb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    from boto3.dynamodb.types import TypeDeserializer
    d = TypeDeserializer()
    return {k: d.deserialize(v) for k, v in item.items()}


def scan_table(table_name: str):
    paginator = dynamodb.get_paginator('scan')
    if CONSISTENT_READ:
        return paginator.paginate(TableName=table_name, ConsistentRead=True)
    return paginator.paginate(TableName=table_name)


def lambda_handler(event, context):
    """Generate CSV from DynamoDB table.

    Accepts optional payload:
      {"filter": {"field": "Symbol", "value": "RELIANCE"}}

    Returns JSON with presigned_url and s3_key.
    """
    logger.info('generate_csv invoked')
    if not S3_BUCKET:
        raise ValueError('S3_BUCKET env var not set')

    # Parse filter from event
    filter_field = None
    filter_value = None
    try:
        if isinstance(event, dict) and event.get('filter'):
            f = event.get('filter')
            filter_field = f.get('field')
            filter_value = f.get('value')
    except Exception:
        logger.exception('Invalid filter in event')

    # Scan table and collect rows that match filter
    iterator = scan_table(TABLE_NAME)
    rows: List[Dict[str, Any]] = []
    count = 0
    for page in iterator:
        for it in page.get('Items', []):
            obj = convert_ddb_item(it)
            count += 1
            if filter_field and filter_value is not None:
                v = obj.get(filter_field)
                if v is None or str(v) != str(filter_value):
                    continue
            rows.append(obj)

    # Build CSV header as union of keys
    header = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                header.append(k)

    timestamp = int(time.time())
    filename = f"export-{timestamp}.csv"
    s3_key = f"{CSV_PREFIX}/{filename}"
    tmp_path = os.path.join(tempfile.gettempdir(), filename)

    # Write CSV to tmp
    with open(tmp_path, 'w', newline='', encoding='utf-8') as cf:
        if header:
            writer = csv.DictWriter(cf, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            for r in rows:
                row = {k: ('' if v is None else str(v)) for k, v in r.items()}
                writer.writerow(row)
        else:
            # No rows matched; write empty file with no headers
            cf.write('')

    # Upload to S3
    s3.upload_file(tmp_path, S3_BUCKET, s3_key, ExtraArgs={'ContentType': 'text/csv'})
    # Generate presigned URL (1 hour)
    presigned = s3.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': s3_key}, ExpiresIn=3600)

    logger.info(f'Wrote {len(rows)} rows to s3://{S3_BUCKET}/{s3_key}')
    return {'status': 'ok', 'count': len(rows), 's3_key': s3_key, 'url': presigned}
