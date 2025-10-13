#!/usr/bin/env python3
"""
extract_errors.py
Reads a JSON file written by `aws logs filter-log-events --output json` and prints
any event messages that contain one of the provided keywords (case-insensitive).
Usage: python extract_errors.py <file.json> [keyword1] [keyword2] ...
Example: python extract_errors.py stt_raw.json 403 Forbidden Alpaca
"""
import sys, json
if len(sys.argv) < 2:
    print('Usage: extract_errors.py <file.json> [keyword1] [keyword2] ...', file=sys.stderr)
    sys.exit(2)
path = sys.argv[1]
keywords = [k.lower() for k in sys.argv[2:]] or ['403','forbidden','error','alpaca']
try:
    raw = open(path, 'rb').read()
    try:
        s = raw.decode('utf-8')
    except Exception:
        s = raw.decode('utf-8','backslashreplace')
    try:
        j = json.loads(s)
    except Exception:
        # fallback: treat as raw text lines
        lines = s.splitlines()
        for i,l in enumerate(lines,1):
            low = l.lower()
            if any(k in low for k in keywords):
                print(f'LINE {i}: ' + l.encode('unicode_escape').decode('ascii'))
        sys.exit(0)
    events = j.get('events', [])
    for idx,e in enumerate(events,1):
        msg = e.get('message','')
        low = msg.lower()
        if any(k in low for k in keywords):
            ts = e.get('timestamp','')
            print(f'EVENT {idx} ts={ts}:')
            print(msg.encode('unicode_escape').decode('ascii'))
            print('-'*80)
except FileNotFoundError:
    print(f'File not found: {path}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error processing {path}: {e}', file=sys.stderr)
    sys.exit(1)
