#!/usr/bin/env python3
"""
Simple DynamoDB full-table exporter to JSON.
Writes a JSON array of items to stdout or to a file.
Usage:
  python tools/export_ddb_to_json.py --table tradebot_signals_table --outfile data.json --region us-east-1

Notes:
- Uses boto3 high-level DynamoDB client scan with paginator.
- Emits plain JSON (DynamoDB types deserialized).
- Reads are eventually-consistent by default; use --consistent to enable ConsistentRead on scan (may cost more).
"""
import argparse
import boto3
import json
from boto3.dynamodb.types import TypeDeserializer

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--table', required=True)
    p.add_argument('--outfile', default='data.json')
    p.add_argument('--region', default='us-east-1')
    p.add_argument('--consistent', action='store_true', help='Use ConsistentRead=True on scan')
    return p.parse_args()


def convert_ddb_item(item):
    d = TypeDeserializer()
    return {k: d.deserialize(v) for k, v in item.items()}


def export_table(table_name, region, outfile, consistent):
    client = boto3.client('dynamodb', region_name=region)
    paginator = client.get_paginator('scan')
    iterator = paginator.paginate(TableName=table_name)
    if consistent:
        iterator = paginator.paginate(TableName=table_name, ConsistentRead=True)

    items = []
    for page in iterator:
        for it in page.get('Items', []):
            items.append(convert_ddb_item(it))

    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(items, f, default=str)
    print(f'Wrote {len(items)} items to {outfile}')


if __name__ == '__main__':
    args = parse_args()
    export_table(args.table, args.region, args.outfile, args.consistent)
