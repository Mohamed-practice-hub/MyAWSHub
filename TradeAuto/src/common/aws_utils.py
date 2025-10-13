import json
import os
import time
import math
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

_secrets_client = None
_s3_client = None
_ses_client = None


def get_secrets_client():
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client("secretsmanager")
    return _secrets_client


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def get_ses_client():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses")
    return _ses_client


def read_secret_json(secret_name: str) -> Dict[str, Any]:
    client = get_secrets_client()
    resp = client.get_secret_value(SecretId=secret_name)
    raw = resp.get("SecretString")
    if not raw and "SecretBinary" in resp:
        raw = resp["SecretBinary"].decode("utf-8")
    return json.loads(raw or "{}")


def s3_key_exists(bucket: str, key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404 or e.response.get("Error", {}).get("Code") in ("404", "NotFound", "NoSuchKey"):
            return False
        raise


def s3_read_json(bucket: str, key: str) -> Optional[Dict[str, Any]]:
    client = get_s3_client()
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read().decode("utf-8")
        return json.loads(body)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise


def s3_write_json(bucket: str, key: str, data: Dict[str, Any]):
    client = get_s3_client()
    body = json.dumps(data, separators=(",", ":"))
    client.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"), ContentType="application/json")


def send_email(subject: str, body: str) -> None:
    source = os.environ.get("SES_FROM")
    to = os.environ.get("SES_TO")
    if not source or not to:
        return
    client = get_ses_client()
    client.send_email(
        Source=source,
        Destination={"ToAddresses": [t.strip() for t in to.split(",") if t.strip()]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body[:100000]}},
        },
    )


def now_epoch_s() -> int:
    return int(time.time())


class Guardrails:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.debounce_seconds = int(os.environ.get("DEBOUNCE_SECONDS", "30"))
        self.min_interval_symbol = int(os.environ.get("MIN_INTERVAL_SAME_SYMBOL_SECONDS", "300"))
        self.max_trades_day = int(os.environ.get("MAX_TRADES_PER_DAY", "20"))

    def _debounce_key(self) -> str:
        return "guardrails/debounce.json"

    def _symbol_key(self, symbol: str) -> str:
        return f"guardrails/symbol/{symbol.upper()}.json"

    def _day_key(self) -> str:
        # yyyy-mm-dd in UTC
        day = time.strftime("%Y-%m-%d", time.gmtime())
        return f"guardrails/daily/{day}.json"

    def check_and_record(self, symbol: str) -> Dict[str, Any]:
        # Debounce
        de_key = self._debounce_key()
        de = s3_read_json(self.bucket, de_key) or {}
        last_ts = int(de.get("last_ts", 0))
        now_ts = now_epoch_s()
        if now_ts - last_ts < self.debounce_seconds:
            return {"allowed": False, "reason": f"debounce:{self.debounce_seconds}s"}

        # Symbol interval
        sy_key = self._symbol_key(symbol)
        sy = s3_read_json(self.bucket, sy_key) or {}
        last_symbol_ts = int(sy.get("last_ts", 0))
        if now_ts - last_symbol_ts < self.min_interval_symbol:
            return {"allowed": False, "reason": f"symbol_interval:{self.min_interval_symbol}s"}

        # Daily cap
        day_key = self._day_key()
        day = s3_read_json(self.bucket, day_key) or {"count": 0}
        if int(day.get("count", 0)) >= self.max_trades_day:
            return {"allowed": False, "reason": f"daily_cap:{self.max_trades_day}"}

        # Record intents
        de["last_ts"] = now_ts
        s3_write_json(self.bucket, de_key, de)
        sy["last_ts"] = now_ts
        s3_write_json(self.bucket, sy_key, sy)
        day["count"] = int(day.get("count", 0)) + 1
        s3_write_json(self.bucket, day_key, day)
        return {"allowed": True}

*** End Patch