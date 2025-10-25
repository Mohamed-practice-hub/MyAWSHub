"""KiteConnect-based auth callback Lambda

Uses the official kiteconnect Python wrapper to exchange request_token for access_token
and stores it in Secrets Manager. Sends Telegram notifications on success/error.

Environment Variables:
  SECRET_NAME           required  Secrets Manager path (e.g., autotrade-kite/credentials)
  TELEGRAM_BOT_TOKEN    optional  Telegram bot token for notifications
  TELEGRAM_CHAT_ID      optional  Chat ID (user or group) to receive notifications

Returns a simple HTML page suitable as a redirect target.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict

import boto3
from kiteconnect import KiteConnect  # requires layer


logger = logging.getLogger()
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)


def _get_secret_json(secret_name: str) -> Dict[str, Any]:
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=secret_name)
    raw = resp.get("SecretString")
    if not raw and "SecretBinary" in resp:
        raw = resp["SecretBinary"].decode("utf-8")
    return json.loads(raw or "{}")


def _put_secret_json(secret_name: str, data: Dict[str, Any]):
    sm = boto3.client("secretsmanager")
    sm.put_secret_value(SecretId=secret_name, SecretString=json.dumps(data, separators=(",", ":")))


def _notify_telegram(title: str, message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    # Keep it simple: send as plain text; escape minimal
    text = f"{title}\n{message}"
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            _ = r.read()
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram notify failed: %s", e)
        return False


def _html(body: str, status: int = 200) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": body,
    }


def lambda_handler(event, context):  # pylint: disable=unused-argument
    secret_name = os.environ.get("SECRET_NAME", "autotrade-kite/credentials")
    qs = (event or {}).get("queryStringParameters") or {}
    request_token = qs.get("request_token")

    logger.info("Incoming KiteConnect auth: request_token_present=%s", bool(request_token))

    if not request_token:
        msg = "Missing request_token in query string."
        _notify_telegram("Kite auth ERROR", msg)
        return _html(f"<h3>{msg}</h3>", 400)

    try:
        # read secrets
        sec = _get_secret_json(secret_name)
        api_key = sec.get("api_key") or sec.get("KITE_API_KEY")
        api_secret = sec.get("api_secret") or sec.get("KITE_API_SECRET")
        if not api_key or not api_secret:
            msg = "Secret is missing api_key/api_secret."
            _notify_telegram("Kite auth ERROR", msg)
            return _html(f"<h3>{msg}</h3>", 500)

        # exchange token using KiteConnect wrapper
        kite = KiteConnect(api_key=api_key)
        sess = kite.generate_session(request_token, api_secret=api_secret)
        access_token = (sess or {}).get("access_token")
        user_id = (sess or {}).get("user_id")
        if not access_token:
            msg = "KiteConnect did not return access_token."
            _notify_telegram("Kite auth ERROR", msg)
            return _html(f"<h3>{msg}</h3>", 500)

        # store
        sec["access_token"] = access_token
        if user_id:
            sec["user_id"] = user_id
        _put_secret_json(secret_name, sec)

        prefix = access_token[:6]
        _notify_telegram("Kite auth OK", f"Access token updated. user_id={user_id} prefix={prefix}")
        return _html(f"<h3>Access token updated. Prefix: {prefix}</h3><p>You can close this tab.</p>", 200)
    except Exception as e:  # noqa: BLE001
        logger.exception("Auth failed")
        # Limit size in Telegram
        emsg = str(e)
        if len(emsg) > 800:
            emsg = emsg[:800] + "…"
        _notify_telegram("Kite auth ERROR", emsg)
        return _html(f"<h3>Error: {emsg}</h3>", 500)
