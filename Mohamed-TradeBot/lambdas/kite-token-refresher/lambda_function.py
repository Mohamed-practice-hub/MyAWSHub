import json
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

import boto3


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


def _get_val(d: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        if k in d and d[k]:
            return str(d[k])
    return None


def _generate_totp(secret: str) -> str:
    # Lazy import to keep cold start lower when not needed
    import pyotp  # type: ignore

    totp = pyotp.TOTP(secret)
    return totp.now()


def _login_and_get_request_token(api_key: str, username: str, password: str, totp_secret: Optional[str], pin: Optional[str]) -> str:
    """
    Automates Zerodha login using Playwright and returns the request_token from the redirect URL.
    Works with either TOTP (preferred) or legacy PIN.
    Requires the Zerodha app's redirect URL configured; we don't need to serve it, we just parse the URL.
    """
    from playwright.sync_api import sync_playwright  # type: ignore

    login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(30000)

        page.goto(login_url)

        # Fill username / password
        # Try a few selector variants for resilience
        selectors_user = ["#userid", "input[name=userid]", "input[name=user_id]", "input#user_id"]
        selectors_pass = ["#password", "input[name=password]"]

        def _fill_one(selectors, value):
            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    el.fill(value)
                    return True
            return False

        if not _fill_one(selectors_user, username):
            raise RuntimeError("Unable to locate username field on Zerodha login page")
        if not _fill_one(selectors_pass, password):
            raise RuntimeError("Unable to locate password field on Zerodha login page")

        # Click login/submit
        # Prefer type=submit, fallback to text
        clicked = False
        for sel in ["button[type=submit]", "button#login", "//button[contains(., 'Login')]"]:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                clicked = True
                break
        if not clicked:
            page.keyboard.press("Enter")

        # 2FA step: TOTP (preferred) or PIN fallback
        # Try to detect a TOTP field first
        totp_code: Optional[str] = None
        if totp_secret:
            totp_code = _generate_totp(totp_secret)

        # Give page a moment to render the 2FA form
        page.wait_for_timeout(1500)

        # Known selectors for TOTP or PIN
        totp_selectors = ["input[name=totp]", "#otp", "input[autocomplete=one-time-code]", "input[type=tel]"]
        pin_selectors = ["input[name=pin]", "#pin"]

        def _fill_if_present(selectors, value) -> bool:
            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    el.fill(value)
                    return True
            return False

        did_2fa = False
        if totp_code and _fill_if_present(totp_selectors, totp_code):
            did_2fa = True
        elif pin and _fill_if_present(pin_selectors, pin):
            did_2fa = True

        if did_2fa:
            # Submit 2FA
            for sel in ["button[type=submit]", "#twofa-form button[type=submit]", "//button[contains(., 'Continue')]"]:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    break
        else:
            # Some accounts may be already authenticated; continue to watch for redirect
            pass

        # Wait until redirect happens and the URL contains request_token
        page.wait_for_url("**request_token=**", timeout=45000)
        final_url = page.url

        # Parse request_token
        qs = parse_qs(urlparse(final_url).query)
        request_token = (qs.get("request_token") or [""])[0]
        if not request_token:
            raise RuntimeError("request_token not found in redirect URL")

        context.close()
        browser.close()
        return request_token


def _exchange_access_token(api_key: str, api_secret: str, request_token: str) -> Dict[str, Any]:
    from kiteconnect import KiteConnect  # type: ignore

    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(request_token, api_secret=api_secret)
    return data


def lambda_handler(event, context):
    secret_name = os.environ.get("SECRET_NAME", "autotrade-kite/credentials")
    ses_to = os.environ.get("SES_TO")  # optional single email address
    ses_from = os.environ.get("SES_FROM") or ses_to  # if not provided, attempt to use same

    try:
        sec = _get_secret_json(secret_name)
        api_key = _get_val(sec, "api_key", "KITE_API_KEY")
        api_secret = _get_val(sec, "api_secret", "KITE_API_SECRET")
        username = _get_val(sec, "username", "user_id", "USER_ID")
        password = _get_val(sec, "password", "PASSWORD")
        totp_secret = _get_val(sec, "totp_secret", "TOTP_SECRET")
        pin = _get_val(sec, "pin", "PIN")

        if not api_key or not api_secret:
            raise RuntimeError("Missing api_key/api_secret in secret")
        if not username or not password:
            raise RuntimeError("Missing username/password in secret")

        request_token = _login_and_get_request_token(api_key, username, password, totp_secret, pin)
        data = _exchange_access_token(api_key, api_secret, request_token)
        access_token = data.get("access_token")
        user_id = data.get("user_id") or username
        if not access_token:
            raise RuntimeError("Failed to obtain access_token from generate_session")

        # Write back into the same secret for compatibility with other lambdas
        sec["access_token"] = access_token
        sec["user_id"] = user_id
        sec["last_refreshed_ts"] = int(time.time())
        _put_secret_json(secret_name, sec)

        # Optional SES email
        if ses_to and ses_from:
            try:
                ses = boto3.client("ses")
                ses.send_email(
                    Source=ses_from,
                    Destination={"ToAddresses": [ses_to]},
                    Message={
                        "Subject": {"Data": "Zerodha access token refreshed"},
                        "Body": {
                            "Text": {"Data": f"Access token refreshed for user {user_id} at {sec['last_refreshed_ts']}"}
                        },
                    },
                )
            except Exception as mail_err:  # do not fail rotation if email fails
                print(f"SES email failed: {mail_err}")

        return {
            "statusCode": 200,
            "body": json.dumps({"ok": True, "user_id": user_id}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"ok": False, "error": str(e)}),
        }
