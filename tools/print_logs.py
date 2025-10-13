#!/usr/bin/env python3
"""
print_logs.py
Reads a JSON file output by `aws logs filter-log-events --output json` and prints
each event.message safely (unicode-escaped) so terminals that can't print emojis
or non-UTF8 bytes won't fail.
Usage: python print_logs.py <path-to-json>
"""
import sys, json
if len(sys.argv) < 2:
    print('Usage: print_logs.py <file.json>', file=sys.stderr)
    sys.exit(2)
path = sys.argv[1]
try:
    raw = open(path, 'rb').read()
    # Try to decode as utf-8, fallback to latin1 then use unicode-escape for safe printing
    try:
        s = raw.decode('utf-8')
    except Exception:
        try:
            s = raw.decode('utf-8', 'backslashreplace')
        except Exception:
            s = raw.decode('latin1', 'backslashreplace')
    # If the file is an array of messages (aws --query events[].message --output text),
    # try splitting lines; otherwise, parse JSON
    try:
        j = json.loads(s)
        # j might be a list of messages (strings) or dict with 'events'
        if isinstance(j, list):
            for item in j:
                if isinstance(item, str):
                    print(item.encode('unicode_escape').decode('ascii'))
                else:
                    print(json.dumps(item).encode('unicode_escape').decode('ascii'))
        elif isinstance(j, dict) and 'events' in j:
            for e in j['events']:
                msg = e.get('message', '')
                print(msg.encode('unicode_escape').decode('ascii'))
        else:
            print(json.dumps(j).encode('unicode_escape').decode('ascii'))
    except Exception:
        # fallback: treat as plain text lines
        for line in s.splitlines():
            print(line.encode('unicode_escape').decode('ascii'))
except FileNotFoundError:
    print(f'File not found: {path}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error reading {path}: {e}', file=sys.stderr)
    sys.exit(1)
