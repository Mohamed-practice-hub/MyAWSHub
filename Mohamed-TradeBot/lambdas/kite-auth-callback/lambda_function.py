import json
import os
import hashlib
import urllib.parse
import urllib.request
from typing import Any, Dict
import logging

import boto3

logger = logging.getLogger()
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)


def _maybe_send_email(access_token_prefix: str, simulate: bool) -> bool:
    """Send a notification email if SES env vars are present.

    Env:
      SES_TO_EMAIL (required for send)
      SES_FROM_EMAIL (optional; defaults to TO)
    """
    to_addr = os.environ.get("SES_TO_EMAIL")
    if not to_addr:
        return False
    from_addr = os.environ.get("SES_FROM_EMAIL") or to_addr
    subject = (
        "autotrade: access token refreshed (SIMULATED)" if simulate else "autotrade: access token refreshed"
    )
    body = (
        f"A new (simulated) access token was stored. Prefix: {access_token_prefix}\n"
        if simulate
        else f"A new access token was stored successfully. Prefix: {access_token_prefix}\n"
    )
    try:
        ses = boto3.client("ses")
        ses.send_email(
            Source=from_addr,
            Destination={"ToAddresses": [to_addr]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info("Notification email sent to %s", to_addr)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to send SES email: %s", e)
        return False


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


def _html(body: str, status: int = 200) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": body,
    }


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Zerodha auth callback (REST-only).

    Modes:
    - simulate=1 : No request_token required; returns a simulated success for console tests.
    - Real exchange: requires request_token; performs checksum POST to Kite API and stores access_token.
    """
    secret_name = os.environ.get("SECRET_NAME", "autotrade-kite/credentials")
    qs = (event or {}).get("queryStringParameters") or {}
    request_token = qs.get("request_token")
    simulate = qs.get("simulate") in ("1", "true", "yes", "True")

    logger.info(
        "Incoming auth callback: simulate=%s request_token_present=%s", simulate, bool(request_token)
    )

    try:
        if simulate:
            # Fast path: do not touch Secrets Manager.
            prefix = "SIMUL"
            email_sent = _maybe_send_email(prefix, True)
            logger.info("SIMULATE_SUCCESS email_sent=%s", email_sent)
            return _html(
                f"<h3>SIMULATED access token (not stored). Prefix: {prefix}{' (email sent)' if email_sent else ''}</h3>"
            )

        # Real path below
        sec = _get_secret_json(secret_name)
        api_key = sec.get("api_key") or sec.get("KITE_API_KEY")
        api_secret = sec.get("api_secret") or sec.get("KITE_API_SECRET")
        if not api_key or not api_secret:
            return _html("<h3>Secret is missing api_key/api_secret.</h3>", 500)
        if not request_token:
            return _html("<h3>Missing request_token in query string.</h3>", 400)

        checksum = hashlib.sha256(
            f"{api_key}{request_token}{api_secret}".encode("utf-8")
        ).hexdigest()
        form = {"api_key": api_key, "request_token": request_token, "checksum": checksum}
        data_bytes = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            url="https://api.kite.trade/session/token",
            data=data_bytes,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "autotrade-lambda/1.0",
                "X-Kite-Version": "3",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Non-JSON response: %s", body[:300])
            return _html(f"<h3>Unexpected response (not JSON): {body[:300]}</h3>", 500)
        if parsed.get("status") != "success":
            logger.error("Error from API: %s", parsed)
            return _html(f"<h3>Error from API: {json.dumps(parsed)[:400]}</h3>", 500)
        data_obj = parsed.get("data") or {}
        access_token = data_obj.get("access_token")
        user_id = data_obj.get("user_id")
        if not access_token:
            return _html("<h3>Missing access_token in API response.</h3>", 500)

        sec["access_token"] = access_token
        if user_id:
            sec["user_id"] = user_id
        _put_secret_json(secret_name, sec)

        prefix = access_token[:6]
        email_sent = _maybe_send_email(prefix, False)
        logger.info("REAL_SUCCESS user_id=%s email_sent=%s", user_id, email_sent)
        return _html(
            f"<h3>Access token updated. Prefix: {prefix}{' (email sent)' if email_sent else ''}</h3><p>You can close this tab.</p>"
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Auth callback failed")
        return _html(f"<h3>Error: {str(e)}</h3>", 500)
