import json
import os
import sys
from typing import Any, Dict

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.common.aws_utils import Guardrails, s3_write_json, send_email  # type: ignore
from src.brokers.zerodha import place_order  # type: ignore

CODE_VERSION = "2025-10-13"

def _json(o: Any) -> str:
    return json.dumps(o, separators=(",", ":"))


def lambda_handler(event, context):
    bucket = os.environ.get("S3_BUCKET")
    auto_execute = os.environ.get("AUTO_EXECUTE", "false").lower() == "true"

    symbol = (event.get("symbol") or event.get("ticker") or "").upper()
    side = (event.get("side") or event.get("action") or "").upper()
    qty = int(event.get("qty") or event.get("quantity") or 0)
    reason = event.get("reason") or event.get("source") or "webhook"
    correlation_id = event.get("id") or event.get("correlation_id") or ""

    if not bucket:
        return {"statusCode": 500, "body": _json({"error": "Missing S3_BUCKET"})}
    if not symbol or side not in ("BUY", "SELL") or qty <= 0:
        return {"statusCode": 400, "body": _json({"error": "Invalid input"})}

    guard = Guardrails(bucket)
    g = guard.check_and_record(symbol)
    if not g.get("allowed"):
        s3_write_json(bucket, f"webhook-trades/{correlation_id or 'noid'}-{symbol}.json", {"symbol": symbol, "side": side, "qty": qty, "reason": reason, "skipped": g})
        return {"statusCode": 200, "body": _json({"message": "Guardrails skipped", "skip": g})}

    result: Dict[str, Any] = {"dry_run": not auto_execute}
    if auto_execute:
        try:
            order = place_order(symbol, side, qty, tag=correlation_id or reason)
            result.update({"order_id": order.get("order_id"), "status": order.get("status")})
        except Exception as e:
            result.update({"error": str(e)})
    else:
        result.update({"message": "dry-run: order not placed"})

    s3_write_json(bucket, f"webhook-trades/{correlation_id or 'noid'}-{symbol}.json", {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "reason": reason,
        "result": result,
        "version": CODE_VERSION,
    })

    send_email(subject=f"tradeauto webhook {symbol} {side} x{qty}", body=_json(result))

    return {"statusCode": 200, "body": _json({"ok": True, "result": result})}
