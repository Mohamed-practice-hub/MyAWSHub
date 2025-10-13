import json
import os
import time
from collections import deque, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone

import boto3

try:
    import urllib.request
    import urllib.parse
except Exception:
    urllib = None

def _now_utc():
    return datetime.now(timezone.utc)

def _iso(dt: datetime):
    return dt.astimezone(timezone.utc).isoformat()

def _request_with_retries(method: str, url: str, *, headers=None, params=None, json_body=None, timeout=10, max_retries=3, backoff_factor=0.5):
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            qurl = url
            if params:
                q = urllib.parse.urlencode(params)
                qurl = f"{url}?{q}"
            req = urllib.request.Request(qurl, method=method.upper())
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            data = None
            if json_body is not None:
                body = json.dumps(json_body).encode('utf-8')
                req.add_header('Content-Type', 'application/json')
                data = body
            with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
                status = resp.getcode()
                txt = resp.read().decode('utf-8')
                return status, (json.loads(txt) if txt else {})
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(backoff_factor * (2 ** attempt))
            else:
                raise

_secrets = None
_s3 = None

def _secrets_client():
    global _secrets
    if _secrets is None:
        _secrets = boto3.client('secretsmanager')
    return _secrets

def _s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client('s3')
    return _s3

def _get_alpaca_headers():
    name = os.environ.get('ALPACA_SECRET_NAME', 'swing-alpaca/papter-trading/keys')
    sec = _secrets_client().get_secret_value(SecretId=name)
    js = json.loads(sec['SecretString'])
    return {
        'APCA-API-KEY-ID': js['ALPACA_API_KEY'],
        'APCA-API-SECRET-KEY': js['ALPACA_SECRET_KEY']
    }

TRADING_URL = os.environ.get('ALPACA_TRADING_URL', 'https://paper-api.alpaca.markets')
S3_BUCKET = os.environ.get('S3_BUCKET', 'swing-automation-data-processor')

def _list_webhook_logs(since: datetime):
    # Logs stored as webhook-trades/YYYY/MM/webhook_*.json
    s3 = _s3_client()
    results = []
    # cover current and previous month prefixes to span 30 days
    months = set()
    cur = since
    end = _now_utc()
    dt = cur
    while dt <= end:
        months.add((dt.year, dt.month))
        dt = dt + timedelta(days=1)
    months.add((end.year, end.month))

    for (y, m) in months:
        prefix = f"webhook-trades/{y:04d}/{m:02d}/"
        token = None
        while True:
            kwargs = dict(Bucket=S3_BUCKET, Prefix=prefix, ContinuationToken=token) if token else dict(Bucket=S3_BUCKET, Prefix=prefix)
            resp = s3.list_objects_v2(**kwargs)
            for obj in resp.get('Contents', []):
                key = obj['Key']
                # fetch object if in window
                b = s3.get_object(Bucket=S3_BUCKET, Key=key)['Body'].read().decode('utf-8')
                try:
                    j = json.loads(b)
                except Exception:
                    continue
                ts = j.get('timestamp')
                try:
                    when = datetime.fromisoformat(ts.replace('Z', '+00:00')) if ts else None
                except Exception:
                    when = None
                if when and when >= since:
                    results.append(j)
            if resp.get('IsTruncated'):
                token = resp.get('NextContinuationToken')
            else:
                break
    return results

def _fetch_orders_30d():
    headers = _get_alpaca_headers()
    # fetch recent orders; Alpaca supports filters but we'll fetch a larger window then filter by date
    url = f"{TRADING_URL}/v2/orders"
    # Pull up to 500 most recent orders (descending)
    status, data = _request_with_retries('GET', url, headers=headers, params={"status": "all", "limit": 500, "direction": "desc"})
    if status < 200 or status >= 300:
        return []
    cutoff = _now_utc() - timedelta(days=30)
    out = []
    for o in data or []:
        created_at = o.get('created_at')
        try:
            cat = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if created_at else None
        except Exception:
            cat = None
        if cat and cat >= cutoff:
            out.append(o)
    return out

def _fetch_fills_30d():
    headers = _get_alpaca_headers()
    cutoff_date = (_now_utc() - timedelta(days=30)).date().isoformat()
    # Use /v2/account/activities/FILL for fills
    url = f"{TRADING_URL}/v2/account/activities/FILL"
    status, data = _request_with_retries('GET', url, headers=headers, params={"after": cutoff_date, "direction": "asc", "page_size": 100})
    if status < 200 or status >= 300:
        return []
    return data or []

def _compute_realized_pl_per_order(fills):
    # FIFO cost basis per symbol. Works for long only; includes basic short handling.
    lots = defaultdict(deque)  # symbol -> deque of (qty_remaining, price)
    realized_by_order = defaultdict(Decimal)

    def D(x):
        try:
            return Decimal(str(x))
        except Exception:
            return Decimal(0)

    for f in fills:
        sym = (f.get('symbol') or '').upper()
        side = (f.get('side') or '').lower()  # 'buy' or 'sell'
        qty = D(f.get('qty'))
        price = D(f.get('price'))
        order_id = f.get('order_id')
        if side == 'buy':
            # reduce short lots first (cover), else add long lot
            remaining = qty
            # If we have negative qty lots to represent shorts, cover them
            while remaining > 0 and lots[sym] and lots[sym][0][0] < 0:
                lot_qty, lot_price = lots[sym][0]
                cover = min(remaining, -lot_qty)
                realized = (lot_price - price) * cover  # short: sold high (lot_price), buy low (price)
                realized_by_order[order_id] += realized
                lot_qty += cover  # toward zero
                remaining -= cover
                if lot_qty == 0:
                    lots[sym].popleft()
                else:
                    lots[sym][0] = (lot_qty, lot_price)
            if remaining > 0:
                lots[sym].append((remaining, price))
        elif side == 'sell':
            # consume long lots; if none, create negative lot (short)
            remaining = qty
            while remaining > 0 and lots[sym] and lots[sym][0][0] > 0:
                lot_qty, lot_price = lots[sym][0]
                take = min(remaining, lot_qty)
                realized = (price - lot_price) * take
                realized_by_order[order_id] += realized
                lot_qty -= take
                remaining -= take
                if lot_qty == 0:
                    lots[sym].popleft()
                else:
                    lots[sym][0] = (lot_qty, lot_price)
            if remaining > 0:
                # entering short position
                lots[sym].append((-remaining, price))
        else:
            # unknown side, skip
            continue

    # round to 2 decimals
    rounded = {k: float(v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) for k, v in realized_by_order.items()}
    return rounded

def _match_reason(orders, logs):
    # index logs by (symbol, action) with timestamp
    idx = []
    for L in logs:
        wd = L.get('webhook_data', {})
        sym = (wd.get('symbol') or '').upper()
        act = (wd.get('action') or '').upper()
        ts = L.get('timestamp')
        try:
            t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except Exception:
            t = None
        idx.append((sym, act, t, wd))

    enriched = []
    for o in orders:
        sym = (o.get('symbol') or '').upper()
        act = (o.get('side') or '').upper()
        filled = o.get('filled_at') or o.get('submitted_at') or o.get('created_at')
        try:
            ot = datetime.fromisoformat(filled.replace('Z', '+00:00')) if filled else None
        except Exception:
            ot = None
        best = None
        best_diff = None
        for (s, a, t, wd) in idx:
            if s == sym and a == act and t and ot:
                diff = abs((ot - t).total_seconds())
                if best_diff is None or diff < best_diff:
                    best = wd
                    best_diff = diff
        reason = None
        if best and best_diff is not None and best_diff <= 600:  # within 10 minutes
            # capture salient fields as rationale
            reason = {
                "source": best.get('source', 'webhook'),
                "signal_price": best.get('price'),
                "signal_volume": best.get('volume'),
                "received_at": best.get('timestamp')
            }
        enriched.append((o, reason))
    return enriched

def lambda_handler(event, context):
    # CORS preflight
    if event.get('requestContext') and event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        }

    try:
        cutoff = _now_utc() - timedelta(days=30)
        orders = _fetch_orders_30d()
        fills = _fetch_fills_30d()
        realized_by_order = _compute_realized_pl_per_order(fills)
        logs = _list_webhook_logs(cutoff)
        enriched = _match_reason(orders, logs)
        records = []
        for (o, reason) in enriched:
            oid = o.get('id')
            realized = realized_by_order.get(oid)
            rec = {
                'order_id': oid,
                'symbol': o.get('symbol'),
                'side': o.get('side'),
                'qty': o.get('qty') or o.get('filled_qty'),
                'status': o.get('status'),
                'submitted_at': o.get('submitted_at'),
                'filled_at': o.get('filled_at'),
                'filled_avg_price': o.get('filled_avg_price'),
                'type': o.get('type'),
                'time_in_force': o.get('time_in_force'),
                'realized_pl': realized,
                'reason': reason or {}
            }
            records.append(rec)
        body = {'since': _iso(cutoff), 'count': len(records), 'records': records}
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(body)
        }
    except Exception as e:
        print(f"Error in history-api: {e}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
