import os
import json
import logging
import boto3
import time
from decimal import Decimal
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
            resp = requests.post(url, data={'chat_id': chat_id, 'text': message}, timeout=5)
            if resp.status_code == 200:
                logger.info('Telegram notification sent successfully')
                return True
            else:
                logger.error(f'Telegram notify failed: status={resp.status_code} body={resp.text}')
                # fallthrough to urllib fallback
        except Exception:
            # fallback using urllib.request to avoid requiring requests
            try:
                from urllib import parse, request
                data = parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
                req = request.Request(url, data=data)
                request.urlopen(req, timeout=5)
                logger.info('Telegram notification sent successfully (urllib fallback)')
                return True
            except Exception as e:
                logger.error(f'Telegram notify failed (urllib fallback): {e}')
    except Exception as e:
        logger.error(f'Telegram notify failed: {e}')
    return False


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
        return False
    return True


# --- EventBridge publish helper -------------------------------------------------
def _get_eventbridge_client():
    """Return a boto3 EventBridge client using configured region."""
    region = os.environ.get('AWS_REGION', 'us-east-1')
    return boto3.client('events', region_name=region)


def _put_events_with_retries(entries, fallback_minimal_entry=None, fallback_lambda_env=None, original_detail=None):
    """
    Attempt to put EventBridge entries with retries and exponential backoff.
    If retries fail, optionally try a fallback minimal EventBridge entry, then
    optionally invoke a fallback Lambda (async) whose name is provided via env var name.

    Returns True on success, False otherwise.
    """
    eventbridge = _get_eventbridge_client()
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info('EventBridge publish attempt %s/%s', attempt, max_attempts)
            resp = eventbridge.put_events(Entries=entries)
            logger.info('EventBridge response: %s', resp)
            if resp.get('FailedEntryCount', 1) == 0:
                return True
            else:
                logger.error('EventBridge reported failures: %s', resp)
        except Exception as e:
            logger.exception('Exception publishing EventBridge event on attempt %s: %s', attempt, e)

        # backoff
        sleep_s = 2 ** attempt
        logger.info('Sleeping %s seconds before retry', sleep_s)
        time.sleep(sleep_s)

    # After retries, attempt fallback minimal publish if provided
    if fallback_minimal_entry:
        try:
            logger.info('Attempting fallback EventBridge publish')
            fr = eventbridge.put_events(Entries=[fallback_minimal_entry])
            logger.info('Fallback EventBridge response: %s', fr)
            if fr.get('FailedEntryCount', 1) == 0:
                return True
        except Exception as e:
            logger.exception('Fallback EventBridge publish failed: %s', e)

    # Last-resort: try invoking a fallback Lambda directly (async) if configured
    if fallback_lambda_env:
        fn = os.environ.get(fallback_lambda_env)
        if fn:
            try:
                logger.info('Invoking fallback Lambda directly: %s', fn)
                lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
                payload = json.dumps(original_detail or {}, default=str)
                lambda_client.invoke(FunctionName=fn, InvocationType='Event', Payload=payload)
                logger.info('Direct Lambda invoke attempted for fallback: %s', fn)
                return True
            except Exception as e:
                logger.exception('Direct Lambda invoke failed (fallback): %s', e)

    return False

# -------------------------------------------------------------------------------


def publish_exporter_event(request_id, status, symbol, traded_date, details=None):
    """
    Publish EventBridge event to trigger exporter after analysis completes.
    Returns True on success, False otherwise.
    """
    # Backwards-compatible, robust publisher. Accepts the original parameter list but
    # also tolerates calls that omit symbol/traded_date/details.
    # Robust publisher: retries, EventBusName support, fallback and direct-lambda invoke
    REGION = os.environ.get('AWS_REGION', 'us-east-1')
    bus = os.environ.get('EVENT_BUS_NAME')
    eventbridge = boto3.client('events', region_name=REGION)

    event_detail = {
        'analysis_request_id': request_id,
        'timestamp': datetime.utcnow().isoformat(),
        'status': status,
        'symbol': symbol,
        'traded_date': traded_date,
        'details': details or {},
        'trigger_exporter': True
    }
    logger.info('Publishing exporter event detail: %s', json.dumps(event_detail, default=str))

    entry = {
        'Source': 'tradebot.analysis',
        'DetailType': 'Analysis Completed',
        'Detail': json.dumps(event_detail, default=str)
    }
    if bus and bus.lower() != 'default':
        entry['EventBusName'] = bus

    payload = [entry]

    # Use centralized helper to publish with retries, fallback EventBridge entry and Lambda invoke
    fallback_detail = {
        'analysis_request_id': request_id,
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'fallback',
        'trigger_exporter': True,
        'fallback': True
    }
    fallback_entry = {
        'Source': 'tradebot.analysis',
        'DetailType': 'Analysis Completed',
        'Detail': json.dumps(fallback_detail, default=str)
    }
    if bus and bus.lower() != 'default':
        entry['EventBusName'] = bus
        fallback_entry['EventBusName'] = bus

    success = _put_events_with_retries(payload, fallback_minimal_entry=fallback_entry, fallback_lambda_env='EXPORTER_LAMBDA_NAME', original_detail=event_detail)
    if success:
        logger.info('Exporter trigger event published (or fallback succeeded)')
        return True

    logger.error('All attempts to trigger exporter failed')
    return False


def publish_fallback_exporter_event(request_id, reason=None):
    """
    Minimal fallback publish for exporter trigger. Returns True on success.
    """
    REGION = os.environ.get('AWS_REGION', 'us-east-1')
    bus = os.environ.get('EVENT_BUS_NAME')
    eventbridge = boto3.client('events', region_name=REGION)
    fallback_detail = {
        'analysis_request_id': request_id,
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'fallback',
        'trigger_exporter': True,
        'fallback': True,
        'reason': str(reason)
    }
    entry = {
        'Source': 'tradebot.analysis',
        'DetailType': 'Analysis Completed',
        'Detail': json.dumps(fallback_detail, default=str)
    }
    if bus and bus.lower() != 'default':
        entry['EventBusName'] = bus

    success = _put_events_with_retries([entry], fallback_lambda_env='EXPORTER_LAMBDA_NAME', original_detail=fallback_detail)
    if success:
        return True
    return False


def update_meta_timestamp():
    """Write DBLastModified to the meta item so the exporter can detect new data."""
    try:
        now_iso = datetime.utcnow().isoformat()
        table.update_item(
            Key={'SymbolKey': '__meta__', 'TradedDate': '__config__'},
            UpdateExpression='SET DBLastModified = :v',
            ExpressionAttributeValues={':v': now_iso}
        )
        logger.info('Wrote DBLastModified meta timestamp: %s', now_iso)
        return True
    except Exception as e:
        logger.error('Failed updating DB meta timestamp: %s', e)
        return False




DDB_TABLE = os.environ.get('DYNAMODB_TABLE', 'tradebot_signals_table')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(DDB_TABLE)

# Indicator helper functions
import math
import re

def ma(series, period):
    if len(series) < period:
        return None
    return sum(series[-period:]) / period

# RSI using average gains/losses
def rsi(series, period=14):
    if len(series) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        delta = series[i] - series[i-1]
        if delta > 0:
            gains += delta
        else:
            losses -= delta
    if gains + losses == 0:
        return 50.0
    rs = (gains / period) / (losses / period) if losses != 0 else float('inf')
    if math.isinf(rs):
        return 100.0
    return 100 - (100 / (1 + rs))

# MACD: EMA12 - EMA26. We'll compute simple EMA
def ema(series, period):
    if len(series) < period:
        return None
    k = 2 / (period + 1)
    ema_prev = sum(series[:period]) / period
    for price in series[period:]:
        ema_prev = (price - ema_prev) * k + ema_prev
    return ema_prev

def macd(series):
    ema12 = ema(series, 12)
    ema26 = ema(series, 26)
    if ema12 is None or ema26 is None:
        return (None, None, None)
    macd_line = ema12 - ema26
    # MACD Signal line (9-period EMA of MACD line) approximate by computing MACD over longer series
    # Simpler: compute MACD series across whole set then EMA9 on it.
    macd_series = []
    # Compute EMA on rolling basis (not efficient but acceptable for small data)
    for i in range(len(series)):
        sub = series[:i+1]
        e12 = ema(sub, 12)
        e26 = ema(sub, 26)
        if e12 is None or e26 is None:
            macd_series.append(None)
        else:
            macd_series.append(e12 - e26)
    macd_series_clean = [v for v in macd_series if v is not None]
    if len(macd_series_clean) < 9:
        return (macd_line, None, None)
    # Compute EMA9 on macd_series_clean
    signal = ema(macd_series_clean, 9)
    hist = None
    if signal is not None and macd_line is not None:
        hist = macd_line - signal
    return (macd_line, signal, hist)

# ATR (Average True Range); uses high/low/close arrays
def atr(highs, lows, closes, period=14):
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if len(trs) < period:
        return None
    # Simple average ATR
    return sum(trs[-period:]) / period

# Compute support signal stub

def compute_signal(macd_line, macd_signal, rsi_val):
    # Improved rules: add confidence scaling and avoid premature SELLs
    if macd_line is None or macd_signal is None or rsi_val is None:
        return ('HOLD', 'LOW')

    # BUY: bullish crossover + not overbought
    if macd_line > macd_signal and rsi_val < 70:
        confidence = 'HIGH' if rsi_val < 60 else 'MEDIUM'
        return ('BUY', confidence)

    # SELL: bearish crossover + overbought
    if macd_line < macd_signal and rsi_val > 70:
        confidence = 'HIGH' if rsi_val > 80 else 'MEDIUM'
        return ('SELL', confidence)

    # HOLD: neutral or conflicting signals
    return ('HOLD', 'LOW')


# --- Helpers for safe trading execution (optional and gated) ---
def _get_kite_client_from_secrets(secret_name=None):
    """Return a KiteConnect client configured with access token from Secrets Manager.
    Caller must handle exceptions. This function expects the secret to contain api_key and access_token.
    """
    try:
        from kiteconnect import KiteConnect
    except Exception:
        logger.warning('KiteConnect library not available in this environment.')
        return None
    secret_name = secret_name or os.environ.get('SECRET_NAME', 'autotrade-kite/credentials')
    sm = boto3.client('secretsmanager')
    sec = sm.get_secret_value(SecretId=secret_name)
    creds = json.loads(sec.get('SecretString') or '{}')
    api_key = creds.get('api_key') or creds.get('KITE_API_KEY')
    access_token = creds.get('access_token')
    if not api_key or not access_token:
        logger.warning('Kite credentials missing in Secrets Manager')
        return None
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def _get_account_balance(kite):
    """Attempt to fetch available cash/balance from Kite. Returns float or None."""
    try:
        # method name may vary depending on KiteConnect version; try margins first
        resp = kite.margins('equity') if hasattr(kite, 'margins') else None
        if resp and isinstance(resp, dict):
            # many implementations include e.g., 'available' or nested structure; best-effort
            for k in ('available', 'available_cash', 'net', 'equity'):
                if k in resp:
                    try:
                        return float(resp.get(k) or 0)
                    except Exception:
                        continue
        # fallback: try profile/holdings endpoints
        if hasattr(kite, 'profile'):
            p = kite.profile()
            if isinstance(p, dict) and p.get('equity'):
                return float(p.get('equity'))
    except Exception as e:
        logger.debug('Account balance fetch failed: %s', e)
    return None


def _has_open_order_for_symbol(kite, tradingsymbol, side=None):
    """Return True if there is an open/triggered order for this tradingsymbol (best-effort)."""
    try:
        orders = kite.orders()
        for o in orders:
            if o.get('tradingsymbol') == tradingsymbol and o.get('status') in ('OPEN', 'TRIGGER PENDING', 'PENDING'):
                if side:
                    if o.get('transaction_type') == side:
                        return True
                else:
                    return True
    except Exception as e:
        logger.debug('Failed to list orders: %s', e)
    return False


def _compute_quantity_from_allocation(price, allocation_pct, available_balance, min_trade_value=100):
    """Compute integer quantity based on percentage allocation of available_balance and current price.
    Returns 0 if allocation too small.
    """
    try:
        allocation_value = (allocation_pct / 100.0) * available_balance
        if allocation_value < min_trade_value:
            return 0
        qty = int(allocation_value / price)
        return max(0, qty)
    except Exception as e:
        logger.debug('Quantity calculation failed: %s', e)
        return 0


def _place_order_with_stop(kite, tradingsymbol, exchange, side, qty, price=None, stop_pct=0.02, trailing=False):
    """Place a primary LIMIT order and a stop-loss order as a separate order (best-effort).
    This function is intentionally cautious and logs failures rather than raising.
    """
    try:
        if qty <= 0:
            logger.info('Quantity computed as 0, skipping order placement for %s', tradingsymbol)
            return None
        # Place LIMIT order (buyer/seller)
        order_params = dict(
            variety='regular',
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            transaction_type=side,
            quantity=qty,
            order_type='LIMIT' if price else 'MARKET',
            product='MIS',
        )
        if price:
            order_params['price'] = round(price, 2)
        logger.info('Placing primary order: %s', order_params)
        resp = kite.place_order(**order_params)
        logger.info('Primary order response: %s', resp)

        # Place stop-loss order as simple SL (best-effort). For BUY, SL will be below; for SELL, SL above.
        if price:
            if side == 'BUY':
                trigger_price = round(price * (1 - stop_pct), 2)
            else:
                trigger_price = round(price * (1 + stop_pct), 2)
            sl_params = dict(
                variety='regular',
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type=('SELL' if side == 'BUY' else 'BUY'),
                quantity=qty,
                order_type='SL',
                trigger_price=trigger_price,
                product='MIS',
            )
            try:
                logger.info('Placing stop-loss order: %s', sl_params)
                sl_resp = kite.place_order(**sl_params)
                logger.info('Stop-loss order response: %s', sl_resp)
            except Exception as e:
                logger.error('Stop-loss placement failed: %s', e)
        return resp
    except Exception as e:
        logger.error('Order placement failed: %s', e)
        return None

# Helper to convert Decimal types
def decimalize(v):
    try:
        return Decimal(str(v))
    except Exception:
        return None

# Main handler: process DynamoDB Stream events, for updated/new items compute indicators and update item

def lambda_handler(event, context):
    # Test mode: if invoked with {"test_notification": true} send a test notification and return
    try:
        if isinstance(event, dict) and event.get('test_notification'):
            msg = event.get('test_message', 'Test notification from tradebot-analysis-lambda')
            notify_telegram(f"[TEST] {msg}")
            notify_email('Test notification from analysis lambda', msg)
            return {'status': 'test_sent'}
    except Exception:
        logger.exception('Failed running test notification')
    # Accept DynamoDB stream events, SQS messages, or a simple list/dict payload for manual testing
    records = []
    # SQS event shape has Records with body containing JSON
    if isinstance(event, dict) and event.get('Records') and isinstance(event.get('Records'), list):
        raw = event.get('Records', [])
        # Normalize SQS: messages have body with JSON string, Dynamo stream has NewImage
        for r in raw:
            if r.get('eventSource') == 'aws:sqs' or r.get('eventSourceARN') and ':sqs:' in r.get('eventSourceARN'):
                try:
                    body = json.loads(r.get('body') or '{}')
                    records.append({'eventName': 'INSERT', 'sqs': True, 'body': body})
                except Exception:
                    continue
            else:
                records.append(r)
    elif isinstance(event, list):
        # Normalize list of simple items into pseudo-stream records
        for itm in event:
            records.append({'eventName': 'INSERT', 'dynamodb': {'NewImage': {k: {'S': str(v)} for k, v in itm.items()}}})
    elif isinstance(event, dict):
        # Single item payload
        records = [{'eventName': 'INSERT', 'dynamodb': {'NewImage': {k: {'S': str(v)} for k, v in event.items()}}}]
    # If invoked with a backfill instruction, run backfill mode
    # Flags: allow forcing updates (override if_not_exists) and executing trades
    override_updates = False
    execute_trades = False
    enable_trading_env = os.environ.get('ENABLE_TRADING', 'false').lower() == 'true'
    if isinstance(event, dict):
        # allow EventBridge to pass {'override': true} to force updates during testing
        override_updates = bool(event.get('override') or event.get('force_update') or os.environ.get('FORCE_UPDATE', 'false').lower() == 'true')
        execute_trades = bool(event.get('execute_trades', False))
    if isinstance(event, dict) and event.get('backfilldays'):
        try:
            backfill_days = int(event.get('backfilldays', 1))
        except Exception:
            backfill_days = 1
        symbols = event.get('symbols')
        # If symbols not provided, derive set of symbols from table (scan projection)
        if not symbols:
            # obtain unique symbols via a scan (projection) - paginated
            symbols = set()
            resp = table.scan(ProjectionExpression='SymbolKey')
            for it in resp.get('Items', []):
                symbols.add(it.get('SymbolKey'))
            while 'LastEvaluatedKey' in resp:
                resp = table.scan(ProjectionExpression='SymbolKey', ExclusiveStartKey=resp['LastEvaluatedKey'])
                for it in resp.get('Items', []):
                    symbols.add(it.get('SymbolKey'))
            symbols = list(symbols)

        logger.info('Running backfill for symbols=%s for last %s days', symbols, backfill_days)
        results = {}
        threshold_date = (datetime.utcnow().date() - timedelta(days=backfill_days-1)).isoformat()
        from boto3.dynamodb.conditions import Key
        for symbol in symbols:
            # Query all items for symbol in ascending TradedDate
            resp = table.query(KeyConditionExpression=Key('SymbolKey').eq(symbol), ScanIndexForward=True)
            items = resp.get('Items', [])
            while 'LastEvaluatedKey' in resp:
                resp = table.query(KeyConditionExpression=Key('SymbolKey').eq(symbol), ExclusiveStartKey=resp['LastEvaluatedKey'], ScanIndexForward=True)
                items.extend(resp.get('Items', []))

            # Filter to items within threshold (>= threshold_date)
            to_process = [it for it in items if it.get('TradedDate') and it.get('TradedDate') >= threshold_date]
            logger.info('Symbol %s total items=%d to process=%d', symbol, len(items), len(to_process))
            # Precompute arrays
            closes_all = [float(x.get('Close', 0)) for x in items]
            highs_all = [float(x.get('High', 0)) for x in items]
            lows_all = [float(x.get('Low', 0)) for x in items]

            updates = 0
            # Iterate through items and update when within the target days
            for idx, item in enumerate(items):
                traded = item.get('TradedDate')
                if not traded or traded < threshold_date:
                    continue
                # compute using history up to idx
                sub_closes = closes_all[:idx+1]
                sub_highs = highs_all[:idx+1]
                sub_lows = lows_all[:idx+1]

                ma20 = ma(sub_closes, 20)
                ma50 = ma(sub_closes, 50)
                ma200 = ma(sub_closes, 200)
                rsi14 = rsi(sub_closes, 14)
                macd_line, macd_signal, macd_hist = macd(sub_closes)
                atr_val = atr(sub_highs, sub_lows, sub_closes, 14)
                signal, confidence = compute_signal(macd_line, macd_signal, rsi14)

                # Build update expression only for missing computed fields
                update_parts = []
                expr_vals = {}
                expr_names = {}
                if ma20 is not None:
                    if override_updates:
                        update_parts.append('MA20 = :ma20')
                    else:
                        update_parts.append('MA20 = if_not_exists(MA20, :ma20)')
                    expr_vals[':ma20'] = decimalize(round(ma20,2))
                if ma50 is not None:
                    if override_updates:
                        update_parts.append('MA50 = :ma50')
                    else:
                        update_parts.append('MA50 = if_not_exists(MA50, :ma50)')
                    expr_vals[':ma50'] = decimalize(round(ma50,2))
                if ma200 is not None:
                    if override_updates:
                        update_parts.append('MA200 = :ma200')
                    else:
                        update_parts.append('MA200 = if_not_exists(MA200, :ma200)')
                    expr_vals[':ma200'] = decimalize(round(ma200,2))
                if rsi14 is not None:
                    if override_updates:
                        update_parts.append('RSI14 = :rsi14')
                    else:
                        update_parts.append('RSI14 = if_not_exists(RSI14, :rsi14)')
                    expr_vals[':rsi14'] = decimalize(round(rsi14,2))
                if macd_line is not None:
                    if override_updates:
                        update_parts.append('MACD = :macd')
                    else:
                        update_parts.append('MACD = if_not_exists(MACD, :macd)')
                    expr_vals[':macd'] = decimalize(round(macd_line,2))
                if macd_signal is not None:
                    if override_updates:
                        update_parts.append('MACDSignal = :macd_sig')
                    else:
                        update_parts.append('MACDSignal = if_not_exists(MACDSignal, :macd_sig)')
                    expr_vals[':macd_sig'] = decimalize(round(macd_signal,2))
                if macd_hist is not None:
                    if override_updates:
                        update_parts.append('MACDHist = :macd_hist')
                    else:
                        update_parts.append('MACDHist = if_not_exists(MACDHist, :macd_hist)')
                    expr_vals[':macd_hist'] = decimalize(round(macd_hist,2))
                if atr_val is not None:
                    if override_updates:
                        update_parts.append('ATR = :atr')
                    else:
                        update_parts.append('ATR = if_not_exists(ATR, :atr)')
                    expr_vals[':atr'] = decimalize(round(atr_val,2))
                # Signal and Confidence
                if override_updates:
                    update_parts.append('Signal = :signal')
                    update_parts.append('Confidence = :conf')
                else:
                    update_parts.append('Signal = if_not_exists(Signal, :signal)')
                    update_parts.append('Confidence = if_not_exists(Confidence, :conf)')
                expr_vals[':signal'] = signal
                expr_vals[':conf'] = confidence

                if not update_parts:
                    continue

                update_expr = 'SET ' + ', '.join(update_parts)
                # reserved names handling - replace only whole-word occurrences so we don't
                # accidentally change names like MACDSignal
                if re.search(r"\bSignal\b", update_expr):
                    expr_names['#sig'] = 'Signal'
                    update_expr = re.sub(r"\bSignal\b", '#sig', update_expr)
                if re.search(r"\bConfidence\b", update_expr):
                    expr_names['#conf'] = 'Confidence'
                    update_expr = re.sub(r"\bConfidence\b", '#conf', update_expr)

                key = {'SymbolKey': item['SymbolKey'], 'TradedDate': item['TradedDate']}
                kwargs = dict(
                    Key=key,
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_vals
                )
                # Ensure ExpressionAttributeNames contains mappings for Signal and Confidence
                expr_names.setdefault('#sig', 'Signal')
                expr_names.setdefault('#conf', 'Confidence')
                kwargs['ExpressionAttributeNames'] = expr_names
                try:
                    table.update_item(**kwargs)
                    updates += 1
                except ClientError as e:
                    logger.error('Backfill UpdateItem failed for %s: %s', key, e)
            results[symbol] = updates
        logger.info('Backfill results: %s', results)
        # Attempt to trigger exporter after backfill completes
        try:
            pub = publish_exporter_event(context.aws_request_id if hasattr(context, 'aws_request_id') else None, 'success', None, None, {'backfill_results': results})
            logger.info('Exporter publish after backfill: %s', pub)
        except Exception as e:
            logger.error('Failed publishing exporter event after backfill: %s', e)
        # Update DB meta timestamp so the exporter can detect new data (EventBridge-only flow)
        try:
            meta_ok = update_meta_timestamp()
            logger.info('Meta update=%s', meta_ok)
        except Exception as e:
            logger.error('Failed to update DB meta timestamp: %s', e)
        return {'status': 'backfill_done', 'results': results}

    # Support a full-table override mode: event can include {'override_all': true, 'confirm': true}
    # If override_all is true but confirm is false (or absent), run a dry-run and report counts without writing.
    if isinstance(event, dict) and event.get('override_all'):
        confirm = bool(event.get('confirm', False))
        logger.info('Running override_all (confirm=%s)', confirm)
        # Determine symbols to process: either event['symbols'] or all symbols from table
        symbols = event.get('symbols') if isinstance(event.get('symbols'), list) and event.get('symbols') else None
        if not symbols:
            # derive unique symbols via a scan (projection)
            symbols = set()
            resp = table.scan(ProjectionExpression='SymbolKey')
            for it in resp.get('Items', []):
                symbols.add(it.get('SymbolKey'))
            while 'LastEvaluatedKey' in resp:
                resp = table.scan(ProjectionExpression='SymbolKey', ExclusiveStartKey=resp['LastEvaluatedKey'])
                for it in resp.get('Items', []):
                    symbols.add(it.get('SymbolKey'))
            symbols = list(symbols)

        total = 0
        updates = 0
        errors = 0
        # Process symbols one-by-one to limit per-invocation work
        for symbol in symbols:
            try:
                # Query all items for symbol in ascending TradedDate
                from boto3.dynamodb.conditions import Key
                resp = table.query(KeyConditionExpression=Key('SymbolKey').eq(symbol), ScanIndexForward=True)
                items = resp.get('Items', [])
                while 'LastEvaluatedKey' in resp:
                    resp = table.query(KeyConditionExpression=Key('SymbolKey').eq(symbol), ExclusiveStartKey=resp['LastEvaluatedKey'], ScanIndexForward=True)
                    items.extend(resp.get('Items', []))

                for item in items:
                    try:
                        total += 1
                        pk_symbol = item.get('SymbolKey')
                        tradedDate = item.get('TradedDate')
                        # Use the already-queried items as the history for computations
                        hist = items
                        closes = [float(x.get('Close', 0)) for x in hist]
                        highs = [float(x.get('High', 0)) for x in hist]
                        lows = [float(x.get('Low', 0)) for x in hist]

                        ma20 = ma(closes, 20)
                        ma50 = ma(closes, 50)
                        ma200 = ma(closes, 200)
                        rsi14 = rsi(closes, 14)
                        macd_line, macd_signal, macd_hist = macd(closes)
                        atr_val = atr(highs, lows, closes, 14)
                        signal, confidence = compute_signal(macd_line, macd_signal, rsi14)

                        # Build UpdateExpression to overwrite analysis fields
                        set_parts = []
                        expr_vals = {}
                        if ma20 is not None:
                            set_parts.append('MA20 = :ma20')
                            expr_vals[':ma20'] = decimalize(round(ma20,2))
                        if ma50 is not None:
                            set_parts.append('MA50 = :ma50')
                            expr_vals[':ma50'] = decimalize(round(ma50,2))
                        if ma200 is not None:
                            set_parts.append('MA200 = :ma200')
                            expr_vals[':ma200'] = decimalize(round(ma200,2))
                        if rsi14 is not None:
                            set_parts.append('RSI14 = :rsi14')
                            expr_vals[':rsi14'] = decimalize(round(rsi14,2))
                        if macd_line is not None:
                            set_parts.append('MACD = :macd')
                            expr_vals[':macd'] = decimalize(round(macd_line,2))
                        if macd_signal is not None:
                            set_parts.append('MACDSignal = :macd_sig')
                            expr_vals[':macd_sig'] = decimalize(round(macd_signal,2))
                        if macd_hist is not None:
                            set_parts.append('MACDHist = :macd_hist')
                            expr_vals[':macd_hist'] = decimalize(round(macd_hist,2))
                        if atr_val is not None:
                            set_parts.append('ATR = :atr')
                            expr_vals[':atr'] = decimalize(round(atr_val,2))
                        # Signal/confidence always set
                        set_parts.append('Signal = :signal')
                        set_parts.append('Confidence = :conf')
                        expr_vals[':signal'] = signal
                        expr_vals[':conf'] = confidence

                        if not set_parts:
                            continue

                        update_expr = 'SET ' + ', '.join(set_parts)
                        # Use ExpressionAttributeNames if needed
                        expr_names = {}
                        if re.search(r"\bSignal\b", update_expr):
                            expr_names['#sig'] = 'Signal'
                            update_expr = re.sub(r"\bSignal\b", '#sig', update_expr)
                        if re.search(r"\bConfidence\b", update_expr):
                            expr_names['#conf'] = 'Confidence'
                            update_expr = re.sub(r"\bConfidence\b", '#conf', update_expr)

                        if confirm:
                            kw = dict(Key={'SymbolKey': pk_symbol, 'TradedDate': tradedDate}, UpdateExpression=update_expr, ExpressionAttributeValues=expr_vals)
                            # Ensure ExpressionAttributeNames contains mappings for Signal and Confidence
                            expr_names.setdefault('#sig', 'Signal')
                            expr_names.setdefault('#conf', 'Confidence')
                            kw['ExpressionAttributeNames'] = expr_names
                            try:
                                table.update_item(**kw)
                                updates += 1
                            except Exception as e:
                                logger.error('Failed to update %s %s: %s', pk_symbol, tradedDate, e)
                                errors += 1
                        else:
                            # dry-run: just count
                            updates += 1
                    except Exception as e:
                        logger.exception('Error processing item in override_all: %s', e)
                        errors += 1
            except Exception as e:
                logger.exception('Error processing symbol %s in override_all: %s', symbol, e)
                errors += 1

        return {'status': 'override_all', 'confirm': confirm, 'total': total, 'would_update': updates, 'errors': errors}

    # Note: scheduled-run and queue-specific handling removed per request. This Lambda now only supports
    # direct-invocation/backfill/override_all and DynamoDB stream-style processing. This prevents accidental
    # EventBridge or SQS triggered aggregated runs.

    logger.info('Received event with %d records', len(records))
    for rec in records:
        # Handle DynamoDB stream-style records (INSERT/MODIFY)
        if rec.get('eventName') not in ('INSERT', 'MODIFY'):
            continue
        newImg = rec.get('dynamodb', {}).get('NewImage')
        if not newImg:
            continue
        # Extract symbol and date
        symbol = newImg.get('SymbolKey', {}).get('S')
        if not symbol:
            continue
        logger.info('Processing symbol %s', symbol)
        # Gather close prices, highs, lows, closes from table (full history for that symbol)
        try:
            # Use Query on the partition key (SymbolKey) with pagination to ensure we get the full history
            from boto3.dynamodb.conditions import Key
            resp = table.query(KeyConditionExpression=Key('SymbolKey').eq(symbol), ScanIndexForward=True)
            items = resp.get('Items', [])
            while 'LastEvaluatedKey' in resp:
                resp = table.query(KeyConditionExpression=Key('SymbolKey').eq(symbol), ExclusiveStartKey=resp['LastEvaluatedKey'], ScanIndexForward=True)
                items.extend(resp.get('Items', []))
            # Sort by TradedDate or Timestamp to ensure chronological order
            items_sorted = sorted(items, key=lambda x: x.get('TradedDate', x.get('Timestamp', '')))
            closes = [float(x.get('Close', 0)) for x in items_sorted]
            highs = [float(x.get('High', 0)) for x in items_sorted]
            lows = [float(x.get('Low', 0)) for x in items_sorted]
        except ClientError as e:
            logger.error('DynamoDB query failed: %s', e)
            continue

        # Determine which analysis fields are missing in the incoming image and only update those
        analysis_keys = ['MA20','MA50','MA200','RSI14','MACD','MACDSignal','MACDHist','Signal','Confidence','ATR']
        missing_keys = [k for k in analysis_keys if k not in newImg]
        tradedDate = newImg.get('TradedDate', {}).get('S')
        if not missing_keys:
            logger.info('All analysis fields present for %s %s, skipping', symbol, tradedDate)
            continue

        # Compute indicators (we compute all, but will only write missing ones)
        ma20 = ma(closes, 20)
        ma50 = ma(closes, 50)
        ma200 = ma(closes, 200)
        rsi14 = rsi(closes, 14)
        macd_line, macd_signal, macd_hist = macd(closes)
        atr_val = atr(highs, lows, closes, 14)

        # Simple signal & confidence
        signal, confidence = compute_signal(macd_line, macd_signal, rsi14)

        # Optionally execute trades based on signal. This is gated by ENABLE_TRADING env var and
        # an explicit execute_trades flag in the event to avoid accidental live orders.
        try:
            if signal in ('BUY', 'SELL') and enable_trading_env and execute_trades:
                # Build tradingsymbol & exchange from SymbolKey (user's convention: may be 'NSE:RELIANCE')
                tradingsymbol = symbol
                exchange = os.environ.get('DEFAULT_EXCHANGE', 'NSE')
                if ':' in symbol:
                    exchange, tradingsymbol = symbol.split(':', 1)

                kite = _get_kite_client_from_secrets()
                if kite is None:
                    logger.warning('Kite client not available; skipping trade execution for %s', symbol)
                else:
                    # check existing open orders to avoid duplicates
                    if _has_open_order_for_symbol(kite, tradingsymbol, side=signal):
                        logger.info('Open order exists for %s %s, skipping duplicate order', tradingsymbol, signal)
                        notify_telegram(f"Skipped duplicate {signal} order for {tradingsymbol} (existing open order)")
                    else:
                        # allocation percent provided via env or default 2%
                        allocation_pct = float(os.environ.get('TRADE_ALLOCATION_PCT', '2'))
                        # get available balance
                        avail = _get_account_balance(kite) or 0.0
                        # get current market price best-effort via kite.ltp if available
                        price = None
                        try:
                            if hasattr(kite, 'ltp'):
                                ltp = kite.ltp(f"{exchange}:{tradingsymbol}")
                                # ltp dict shape depends on API; best-effort read
                                for v in ltp.values():
                                    if isinstance(v, dict) and v.get('last_price'):
                                        price = float(v.get('last_price'))
                                        break
                        except Exception as e:
                            logger.debug('Failed to fetch ltp for %s: %s', tradingsymbol, e)

                        # The stream handler earlier does not expose a local 'item' variable; pick the current item for this tradedDate
                        current_item = None
                        try:
                            # items (queried above) are ordered; find the item with matching TradedDate if present
                            current_item = next((it for it in items_sorted if it.get('TradedDate') == tradedDate), None)
                        except Exception:
                            current_item = None

                        fallback_price = 0.0
                        if current_item:
                            try:
                                fallback_price = float(current_item.get('Close', 0) or 0)
                            except Exception:
                                fallback_price = 0.0

                        qty = _compute_quantity_from_allocation(price or fallback_price, allocation_pct, avail)
                        if qty <= 0:
                            logger.info('Computed qty 0 for %s using allocation %s%% and available %s, skipping', tradingsymbol, allocation_pct, avail)
                            notify_telegram(f"Not placing {signal} for {tradingsymbol}: allocation too small or insufficient balance.")
                        else:
                            res = _place_order_with_stop(kite, tradingsymbol, exchange, signal, qty, price=price, stop_pct=float(os.environ.get('DEFAULT_SL_PCT', '0.02')))
                            if res:
                                notify_telegram(f"Placed {signal} order for {tradingsymbol} qty={qty} confidence={confidence}")
                                # Optionally write order marker back to DynamoDB to avoid duplicates in future
                                if override_updates:
                                    try:
                                        table.update_item(Key={'SymbolKey': symbol, 'TradedDate': tradedDate}, UpdateExpression='SET LastOrder = :o', ExpressionAttributeValues={':o': json.dumps({'side': signal, 'qty': qty, 'resp': res})})
                                    except Exception as e:
                                        logger.error('Failed writing LastOrder marker: %s', e)
                            else:
                                notify_telegram(f"Failed placing {signal} order for {tradingsymbol} (see logs)")
        except Exception as e:
            logger.exception('Error during trade execution logic: %s', e)

        # Build update expression only for missing computed fields
        update_parts = []
        expr_vals = {}

        if 'MA20' in missing_keys and ma20 is not None:
            update_parts.append('MA20 = if_not_exists(MA20, :ma20)')
            expr_vals[':ma20'] = decimalize(round(ma20,2))
        if 'MA50' in missing_keys and ma50 is not None:
            update_parts.append('MA50 = if_not_exists(MA50, :ma50)')
            expr_vals[':ma50'] = decimalize(round(ma50,2))
        if 'MA200' in missing_keys and ma200 is not None:
            update_parts.append('MA200 = if_not_exists(MA200, :ma200)')
            expr_vals[':ma200'] = decimalize(round(ma200,2))
        if 'RSI14' in missing_keys and rsi14 is not None:
            update_parts.append('RSI14 = if_not_exists(RSI14, :rsi14)')
            expr_vals[':rsi14'] = decimalize(round(rsi14,2))
        if 'MACD' in missing_keys and macd_line is not None:
            update_parts.append('MACD = if_not_exists(MACD, :macd)')
            expr_vals[':macd'] = decimalize(round(macd_line,2))
        if 'MACDSignal' in missing_keys and macd_signal is not None:
            update_parts.append('MACDSignal = if_not_exists(MACDSignal, :macd_sig)')
            expr_vals[':macd_sig'] = decimalize(round(macd_signal,2))
        if 'MACDHist' in missing_keys and macd_hist is not None:
            update_parts.append('MACDHist = if_not_exists(MACDHist, :macd_hist)')
            expr_vals[':macd_hist'] = decimalize(round(macd_hist,2))
        if 'Signal' in missing_keys and signal is not None:
            update_parts.append('Signal = if_not_exists(Signal, :signal)')
            expr_vals[':signal'] = signal
        if 'Confidence' in missing_keys and confidence is not None:
            update_parts.append('Confidence = if_not_exists(Confidence, :conf)')
            expr_vals[':conf'] = confidence
        if 'ATR' in missing_keys and atr_val is not None:
            update_parts.append('ATR = if_not_exists(ATR, :atr)')
            expr_vals[':atr'] = decimalize(round(atr_val,2))

        if not update_parts:
            logger.info('No computed values to write for %s %s, skipping', symbol, tradedDate)
            continue

        update_expr = 'SET ' + ', '.join(update_parts)

        # Handle reserved keywords (e.g., 'Signal' and 'Confidence') by using ExpressionAttributeNames
        expr_names = {}
        if re.search(r"\bSignal\b", update_expr):
            expr_names['#sig'] = 'Signal'
            update_expr = re.sub(r"\bSignal\b", '#sig', update_expr)
        if re.search(r"\bConfidence\b", update_expr):
            expr_names['#conf'] = 'Confidence'
            update_expr = re.sub(r"\bConfidence\b", '#conf', update_expr)

        # Update the item(s) - it depends on key schema; assume primary key is SymbolKey + TradedDate
        tradedDate = newImg.get('TradedDate', {}).get('S')
        pk = symbol
        sk = tradedDate
        try:
            kwargs = dict(
                Key={'SymbolKey': pk, 'TradedDate': sk},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_vals
            )
            if expr_names:
                kwargs['ExpressionAttributeNames'] = expr_names
            # Ensure ExpressionAttributeNames contains mappings for Signal and Confidence
            kwargs.setdefault('ExpressionAttributeNames', {})
            kwargs['ExpressionAttributeNames'].setdefault('#sig', 'Signal')
            kwargs['ExpressionAttributeNames'].setdefault('#conf', 'Confidence')
            table.update_item(**kwargs)
            logger.info('Updated indicators for %s %s', symbol, tradedDate)
            # After update (or even in dry runs), send a notification report for this symbol/date
            try:
                # Build a concise report
                report = f"Analysis report for {symbol} {tradedDate}: Signal={signal}, Confidence={confidence}, MA20={ma20}, MA50={ma50}, RSI14={rsi14}"
                t_ok = notify_telegram(report)
                e_ok = notify_email(f"Analysis report: {symbol} {tradedDate}", report)
                logger.info('Notification results: telegram=%s ses=%s', t_ok, e_ok)
                # After notifications, attempt to trigger exporter the same way fetch triggers analysis
                try:
                    published = publish_exporter_event(context.aws_request_id if hasattr(context, 'aws_request_id') else None, 'success', symbol, tradedDate, {'signal': signal, 'confidence': confidence})
                    logger.info('Published exporter event: %s', published)
                except Exception as e:
                    logger.error('Failed to publish exporter event: %s', e)
                # Update DB meta timestamp so the exporter can detect new data (EventBridge-only flow)
                try:
                    meta_ok = update_meta_timestamp()
                    logger.info('Meta update=%s', meta_ok)
                except Exception as e:
                    logger.error('Failed to update DB meta timestamp: %s', e)
            except Exception:
                logger.exception('Failed sending analysis notifications')
        except ClientError as e:
            logger.error('UpdateItem failed: %s', e)
    return {'status': 'done'}
