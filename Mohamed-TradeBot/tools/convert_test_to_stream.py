#!/usr/bin/env python3
import json
import sys
import re

NUM_RE = re.compile(r'^-?\d+(?:\.\d+)?$')

def is_number_str(s):
    if isinstance(s, (int, float)):
        return True
    if isinstance(s, str) and NUM_RE.match(s):
        return True
    return False


def to_dynamodb_value(v):
    if is_number_str(v):
        return {"N": str(v)}
    else:
        return {"S": str(v)}


def convert(inpath, outpath):
    with open(inpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit('Input JSON must be a list of objects')

    records = []
    for i, item in enumerate(data, start=1):
        newimage = {}
        for k, v in item.items():
            newimage[k] = to_dynamodb_value(v)
        rec = {
            "eventID": str(i),
            "eventName": "INSERT",
            "dynamodb": {"NewImage": newimage}
        }
        records.append(rec)

    out = {"Records": records}
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    print(f'Wrote {outpath} with {len(records)} records')


if __name__ == '__main__':
    inpath = sys.argv[1] if len(sys.argv) > 1 else 'dashboard/test_data.json'
    outpath = sys.argv[2] if len(sys.argv) > 2 else 'stream_event.json'
    convert(inpath, outpath)
