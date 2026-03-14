"""Shared utility functions for the Etsy integration."""

from datetime import datetime


def build_transaction_detail(transaction: dict) -> dict:
    """Build a formatted transaction detail dict from raw API transaction data."""
    price = transaction.get("price", {})
    amount = float(price.get("amount", 0)) / 100 if price.get("amount") else 0
    currency = price.get("currency_code", "USD")

    created_date = None
    if transaction.get("created_timestamp"):
        try:
            created_date = datetime.fromtimestamp(
                transaction["created_timestamp"]
            ).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            created_date = transaction.get("created_timestamp")

    updated_date = None
    if transaction.get("updated_timestamp"):
        try:
            updated_date = datetime.fromtimestamp(
                transaction["updated_timestamp"]
            ).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            updated_date = transaction.get("updated_timestamp")

    variations = []
    for variation in transaction.get("variations", []):
        variations.append({
            "property": variation.get("formatted_name", ""),
            "value": variation.get("formatted_value", ""),
        })

    return {
        "transaction_id": str(transaction.get("transaction_id", "")),
        "title": transaction.get("title"),
        "listing_id": str(transaction.get("listing_id", "")),
        "buyer_user_id": str(transaction.get("buyer_user_id", "")),
        "quantity": transaction.get("quantity"),
        "price_amount": amount,
        "price_currency": currency,
        "variations": variations,
        "created_date": created_date,
        "updated_date": updated_date,
    }
