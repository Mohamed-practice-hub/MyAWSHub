import json
import os
import sys
from typing import Any, Dict

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.common.aws_utils import send_email  # type: ignore
from src.brokers.zerodha import get_positions, get_holdings  # type: ignore


def _json(o: Any) -> str:
    return json.dumps(o, separators=(",", ":"))


def lambda_handler(event, context):
    try:
        positions = get_positions()
        holdings = get_holdings()
        body = _json({"positions": positions, "holdings": holdings})
        send_email(subject="tradeauto portfolio report", body=body)
        return {"statusCode": 200, "body": body}
    except Exception as e:
        return {"statusCode": 500, "body": _json({"error": str(e)})}
