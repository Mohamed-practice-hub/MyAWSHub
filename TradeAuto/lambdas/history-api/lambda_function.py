import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.common.aws_utils import s3_read_json  # type: ignore
from src.brokers.zerodha import get_orders  # type: ignore


def _json(o: Any) -> str:
    return json.dumps(o, separators=(",", ":"))


def _cors_headers():
    origin = os.environ.get("ALLOW_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _merge_reason_from_s3(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket = os.environ.get("S3_BUCKET")
    merged = []
    if not bucket:
        return orders
    for od in orders:
        symbol = od.get("tradingsymbol") or od.get("symbol") or ""
        tag = (od.get("tag") or "").strip()
        corr = tag if tag and tag != "tradeauto" else "noid"
        key = f"webhook-trades/{corr}-{symbol}.json"
        info = s3_read_json(bucket, key) or {}
        od2 = dict(od)
        if info:
            od2["reason"] = info.get("reason")
        merged.append(od2)
    return merged


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": _cors_headers(), "body": ""}
    try:
        orders = get_orders()
        # Filter last 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent = []
        for od in orders:
            ts_str = od.get("order_timestamp") or od.get("exchange_timestamp") or ""
            dt = None
            try:
                if ts_str:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                dt = None
            if dt and dt >= cutoff:
                recent.append(od)
        merged = _merge_reason_from_s3(recent)
        body = _json({"count": len(merged), "orders": merged})
        return {"statusCode": 200, "headers": _cors_headers(), "body": body}
    except Exception as e:
        return {"statusCode": 500, "headers": _cors_headers(), "body": _json({"error": str(e)})}
