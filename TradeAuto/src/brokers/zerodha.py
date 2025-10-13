import os
from typing import Any, Dict, List, Optional

from kiteconnect import KiteConnect
from ..common.aws_utils import read_secret_json

_kite: Optional[KiteConnect] = None
_kite_user_id: Optional[str] = None


def get_kite() -> KiteConnect:
    global _kite, _kite_user_id
    if _kite is not None:
        return _kite

    secret_name = os.environ.get("KITE_SECRET_NAME", "tradeauto-kite/credentials")
    sec = read_secret_json(secret_name)
    api_key = sec.get("api_key")
    access_token = sec.get("access_token")
    user_id = sec.get("user_id")
    if not api_key or not access_token:
        raise RuntimeError("Kite credentials missing: api_key/access_token")
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    _kite = kite
    _kite_user_id = user_id
    return kite


def place_order(symbol: str, side: str, qty: int, price: Optional[float] = None, product: str = "MIS", order_type: str = "MARKET", tag: Optional[str] = None) -> Dict[str, Any]:
    """
    side: BUY or SELL
    product: CNC/MIS/NRML per Zerodha
    order_type: MARKET/LIMIT
    tag: optional string to associate reason/correlation
    """
    kite = get_kite()
    tradingsymbol = symbol.upper()
    transaction_type = KiteConnect.TRANSACTION_TYPE_BUY if side.upper() == "BUY" else KiteConnect.TRANSACTION_TYPE_SELL
    variety = KiteConnect.VARIETY_REGULAR
    params = dict(
        exchange=KiteConnect.EXCHANGE_NSE,
        tradingsymbol=tradingsymbol,
        transaction_type=transaction_type,
        quantity=qty,
        product=product,
        order_type=KiteConnect.ORDER_TYPE_MARKET if order_type == "MARKET" else KiteConnect.ORDER_TYPE_LIMIT,
        variety=variety,
        tag=tag or "tradeauto",
    )
    if params["order_type"] == KiteConnect.ORDER_TYPE_LIMIT and price is not None:
        params["price"] = float(price)
    order = kite.place_order(**params)
    return {"order_id": order.get("order_id"), "status": "submitted", "symbol": tradingsymbol}


def get_orders() -> List[Dict[str, Any]]:
    kite = get_kite()
    return kite.orders()


def get_positions() -> Dict[str, Any]:
    kite = get_kite()
    return kite.positions()


def get_holdings() -> List[Dict[str, Any]]:
    kite = get_kite()
    return kite.holdings()
