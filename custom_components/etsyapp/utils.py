"""Shared utility functions for the Etsy integration."""

from datetime import datetime
from typing import Any


def format_money(money_obj: dict | None) -> dict | None:
    """Convert an Etsy money object to a flat {amount, currency_code} dict.

    Etsy returns money as {amount, divisor, currency_code}. The divisor is
    usually 100 but isn't guaranteed by the API, so we honor it explicitly.
    Returns None if the input is missing or unparseable so callers can omit
    the attribute cleanly.
    """
    if not money_obj:
        return None
    amount = money_obj.get("amount")
    divisor = money_obj.get("divisor") or 100
    if amount is None:
        return None
    try:
        value = float(amount) / float(divisor)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return {
        "amount": round(value, 2),
        "currency_code": money_obj.get("currency_code", "USD"),
    }


def _format_timestamp(ts: Any) -> str | None:
    """Format a Unix timestamp as YYYY-MM-DD HH:MM:SS, or return None."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return None


def build_transaction_detail(transaction: dict) -> dict:
    """Build a formatted transaction detail dict from raw API transaction data."""
    price = transaction.get("price", {})
    amount = float(price.get("amount", 0)) / 100 if price.get("amount") else 0
    currency = price.get("currency_code", "USD")

    variations = []
    for variation in transaction.get("variations", []):
        variations.append({
            "property": variation.get("formatted_name", ""),
            "value": variation.get("formatted_value", ""),
        })

    return {
        "transaction_id": str(transaction.get("transaction_id", "")),
        "receipt_id": str(transaction.get("receipt_id", "")),
        "title": transaction.get("title"),
        "listing_id": str(transaction.get("listing_id", "")),
        "buyer_user_id": str(transaction.get("buyer_user_id", "")),
        "quantity": transaction.get("quantity"),
        "price_amount": amount,
        "price_currency": currency,
        "variations": variations,
        "created_date": _format_timestamp(transaction.get("created_timestamp")),
        "updated_date": _format_timestamp(transaction.get("updated_timestamp")),
    }


def build_receipt_summary(receipt: dict, payment: dict | None = None) -> dict:
    """Build the attribute dict for a single receipt, used by sensor entities.

    Preserves the legacy EtsyLastOrder attribute keys (receipt_id,
    buyer_user_id, order_total, currency_code, order_date, item_count, items)
    so existing user templates/dashboards keep working. order_total stays
    items-only (subtotal); use the explicit subtotal/grandtotal/amount_net
    keys when a different figure is needed.

    Optional fields (buyer_name, message_from_buyer, payment-derived amounts)
    are omitted when null so attribute-row cards skip them cleanly.
    """
    transactions = receipt.get("transactions") or []
    items = [build_transaction_detail(t) for t in transactions]

    subtotal_money = format_money(receipt.get("subtotal"))
    grandtotal_money = format_money(receipt.get("grandtotal"))
    shipping_money = format_money(receipt.get("total_shipping_cost"))
    tax_money = format_money(receipt.get("total_tax_cost"))
    discount_money = format_money(receipt.get("discount_amt"))

    # Items-only subtotal computed from transactions, kept as the canonical
    # order_total for backward compatibility with existing templates.
    items_subtotal = sum(
        (item["price_amount"] or 0) * (item.get("quantity") or 1)
        for item in items
    )

    currency = (
        (grandtotal_money or subtotal_money or {}).get("currency_code")
        or (items[0]["price_currency"] if items else "USD")
    )

    order_date = _format_timestamp(receipt.get("created_timestamp"))
    if not order_date and items:
        order_date = min(
            (item["created_date"] for item in items if item.get("created_date")),
            default=None,
        )

    summary: dict[str, Any] = {
        "receipt_id": str(receipt.get("receipt_id", "")),
        "buyer_user_id": str(receipt.get("buyer_user_id", "")),
        "order_total": round(items_subtotal, 2),
        "currency_code": currency,
        "order_date": order_date,
        "item_count": len(items),
        "items": items,
    }

    # Receipt status fields (omitted on synthesized receipts from the
    # legacy fallback path where receipts data isn't available)
    if receipt.get("status") is not None:
        summary["status"] = receipt["status"]
    if receipt.get("is_paid") is not None:
        summary["is_paid"] = receipt["is_paid"]
    if receipt.get("is_shipped") is not None:
        summary["is_shipped"] = receipt["is_shipped"]

    # Optional buyer name (may be null for some sellers per Etsy 2024 policy)
    buyer_name = receipt.get("name")
    if buyer_name:
        summary["buyer_name"] = buyer_name

    message = receipt.get("message_from_buyer")
    if message:
        summary["message_from_buyer"] = message

    if receipt.get("is_gift"):
        summary["is_gift"] = True
        gift_message = receipt.get("gift_message")
        if gift_message:
            summary["gift_message"] = gift_message

    # Receipt-level totals (split out so templates can use them directly)
    if subtotal_money:
        summary["subtotal"] = subtotal_money["amount"]
    if grandtotal_money:
        summary["grandtotal"] = grandtotal_money["amount"]
    if shipping_money:
        summary["total_shipping_cost"] = shipping_money["amount"]
    if tax_money:
        summary["total_tax_cost"] = tax_money["amount"]
    if discount_money and discount_money["amount"]:
        summary["discount_amount"] = discount_money["amount"]

    # Payment-derived figures (only present when payment was fetched)
    if payment:
        gross = format_money(payment.get("amount_gross"))
        fees = format_money(payment.get("amount_fees"))
        net = format_money(payment.get("amount_net"))
        if gross:
            summary["amount_gross"] = gross["amount"]
        if fees:
            summary["amount_fees"] = fees["amount"]
        if net:
            summary["amount_net"] = net["amount"]

    return summary
