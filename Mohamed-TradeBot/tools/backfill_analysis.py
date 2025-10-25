#!/usr/bin/env python3
"""
Backfill technical indicators for a given symbol in the DynamoDB table.
Usage: python tools/backfill_analysis.py RELIANCE

This script queries the table by SymbolKey, computes indicators (MA20, MA50, MA200, RSI14, MACD, ATR),
and updates the items with those values.
"""
import sys
import time
import os
import boto3
from decimal import Decimal
import math

DDB_TABLE = os.environ.get('DYNAMODB_TABLE', 'tradebot_signals_table')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Indicator functions (same algorithms as Lambda)

def ma(series, period):
    if len(series) < period:
        return None
    return sum(series[-period:]) / period

# RSI
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

# EMA helper
def ema(series, period):
    if len(series) < period:
        return None
    k = 2 / (period + 1)
    ema_prev = sum(series[:period]) / period
    for price in series[period:]:
        ema_prev = (price - ema_prev) * k + ema_prev
    return ema_prev

# MACD
def macd(series):
    ema12 = ema(series, 12)
    ema26 = ema(series, 26)
    if ema12 is None or ema26 is None:
        return (None, None, None)
    macd_line = ema12 - ema26
    # compute macd series to derive signal
    macd_series = []
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
    signal = ema(macd_series_clean, 9)
    hist = None
    if signal is not None and macd_line is not None:
        hist = macd_line - signal
    return (macd_line, signal, hist)

# ATR
def atr(highs, lows, closes, period=14):
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period

# Simple signal
def compute_signal(macd_line, macd_signal, rsi_val):
    if macd_line is None or macd_signal is None or rsi_val is None:
        return ('HOLD', 'LOW')
    if macd_line > macd_signal and rsi_val < 70:
        return ('BUY', 'MEDIUM')
    if macd_line < macd_signal and rsi_val > 30:
        return ('SELL', 'MEDIUM')
    return ('HOLD', 'LOW')


def decimalize(v):
    try:
        return Decimal(str(round(v, 2)))
    except Exception:
        return None


def main(symbol):
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    from boto3.dynamodb.conditions import Key
    table = dynamodb.Table(DDB_TABLE)

    print(f'Querying DynamoDB for symbol {symbol}...')
    # Get all items for the symbol, ascending by TradedDate
    resp = table.query(
        KeyConditionExpression=Key('SymbolKey').eq(symbol),
        ScanIndexForward=True
    )
    items = resp.get('Items', [])
    # handle pagination
    while 'LastEvaluatedKey' in resp:
        resp = table.query(
            KeyConditionExpression=Key('SymbolKey').eq(symbol),
            ExclusiveStartKey=resp['LastEvaluatedKey'],
            ScanIndexForward=True
        )
        items.extend(resp.get('Items', []))

    print(f'Found {len(items)} items for {symbol}')
    if not items:
        return

    # Build series arrays
    closes = [float(x.get('Close', 0)) for x in items]
    highs = [float(x.get('High', 0)) for x in items]
    lows = [float(x.get('Low', 0)) for x in items]

    updates = 0
    # For each item, compute indicators using history up to and including that item
    for idx, item in enumerate(items):
        # For the window, take closes up to idx+1
        sub_closes = closes[:idx+1]
        sub_highs = highs[:idx+1]
        sub_lows = lows[:idx+1]

        ma20 = ma(sub_closes, 20)
        ma50 = ma(sub_closes, 50)
        ma200 = ma(sub_closes, 200)
        rsi14 = rsi(sub_closes, 14)
        macd_line, macd_signal, macd_hist = macd(sub_closes)
        atr_val = atr(sub_highs, sub_lows, sub_closes, 14)
        signal, confidence = compute_signal(macd_line, macd_signal, rsi14)

        # Build update expression; we will overwrite to backfill
        update_parts = []
        expr_vals = {}
        expr_names = {}

        if ma20 is not None:
            update_parts.append('MA20 = :ma20')
            expr_vals[':ma20'] = decimalize(ma20)
        if ma50 is not None:
            update_parts.append('MA50 = :ma50')
            expr_vals[':ma50'] = decimalize(ma50)
        if ma200 is not None:
            update_parts.append('MA200 = :ma200')
            expr_vals[':ma200'] = decimalize(ma200)
        if rsi14 is not None:
            update_parts.append('RSI14 = :rsi14')
            expr_vals[':rsi14'] = decimalize(rsi14)
        if macd_line is not None:
            update_parts.append('MACD = :macd')
            expr_vals[':macd'] = decimalize(macd_line)
        if macd_signal is not None:
            update_parts.append('MACDSignal = :macd_sig')
            expr_vals[':macd_sig'] = decimalize(macd_signal)
        if macd_hist is not None:
            update_parts.append('MACDHist = :macd_hist')
            expr_vals[':macd_hist'] = decimalize(macd_hist)
        if atr_val is not None:
            update_parts.append('ATR = :atr')
            expr_vals[':atr'] = decimalize(atr_val)

        # Signal is a reserved word; use ExpressionAttributeNames
        update_parts.append('#S = :signal')
        expr_names['#S'] = 'Signal'
        expr_vals[':signal'] = signal

        update_parts.append('Confidence = :conf')
        expr_vals[':conf'] = confidence

        if not update_parts:
            continue

        update_expr = 'SET ' + ', '.join(update_parts)

        key = {'SymbolKey': item['SymbolKey'], 'TradedDate': item['TradedDate']}
        kwargs = {
            'Key': key,
            'UpdateExpression': update_expr,
            'ExpressionAttributeValues': {k: v for k, v in expr_vals.items()}
        }
        if expr_names:
            kwargs['ExpressionAttributeNames'] = expr_names

        try:
            table.update_item(**kwargs)
            updates += 1
        except Exception as e:
            print(f'Update failed for {key}: {e}')
        # Throttle a bit
        time.sleep(0.02)

    print(f'Backfill complete for {symbol}: updated {updates} items')

    # Print last 10 items in descending order
    resp = table.query(
        KeyConditionExpression=Key('SymbolKey').eq(symbol),
        ScanIndexForward=False,
        Limit=10
    )
    print('\nLatest 10 items (desc):')
    for it in resp.get('Items', []):
        print(it)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python tools/backfill_analysis.py <SYMBOL>')
        sys.exit(1)
    sym = sys.argv[1]
    main(sym)
