"""Constants for the Etsy integration."""

DOMAIN = "etsyapp"
ETSY_API_BASE = "https://openapi.etsy.com/v3/application"
UPDATE_INTERVAL_SECONDS = 300  # RATE LIMIT VARIES BY ENDPOINT
API_FETCH_LIMIT = 10  # Limit for listings and transactions fetched from API

# Connection modes
CONNECTION_MODE_DIRECT = "direct"
CONNECTION_MODE_PROXY = "proxy"

# Configuration keys
CONF_CONNECTION_MODE = "connection_mode"
CONF_PROXY_URL = "proxy_url"
CONF_PROXY_API_KEY = "proxy_api_key"
CONF_HMAC_SECRET = "hmac_secret"
ETSY_ORDER_STATUSES = {
    "open": "Order placed, awaiting payment",
    "paid": "Payment received, processing",
    "completed": "Order completed",
    "processing": "Order being processed",
    "shipped": "Order shipped",
    "delivered": "Order delivered",
    "cancelled": "Order cancelled",
    "refunded": "Order refunded",
}
ETSY_LISTING_STATES = {
    "active": "Available for purchase",
    "removed": "Removed from shop",
    "sold_out": "Out of stock",
    "expired": "Listing expired",
    "edit": "Being edited",
    "create": "Being created",
    "private": "Private listing",
    "unavailable": "Temporarily unavailable",
}


class EtsyShop:
    """Representation of an Etsy shop."""

    def __init__(
        self,
        shop_id=None,
        shop_name="Unknown Shop",
        currency_code="USD",
        listing_count=0,
        digital_listing_count=0,
        active_listing_count=0,
        sale_count=0,
        average_rating=0.0,
        num_favorers=0,
        last_updated=None,
    ):
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.currency_code = currency_code
        self.listing_count = listing_count
        self.digital_listing_count = digital_listing_count
        self.active_listing_count = active_listing_count
        self.sale_count = sale_count
        self.average_rating = average_rating
        self.num_favorers = num_favorers
        self.last_updated = last_updated


EMPTY_SHOP = EtsyShop(
    shop_id=None,
    shop_name="No Shop Data",
    currency_code="USD",
    listing_count=0,
    digital_listing_count=0,
    active_listing_count=0,
    sale_count=0,
    average_rating=0.0,
    num_favorers=0,
    last_updated=None,
)
EMPTY_ATTRIBUTES = {
    "active_listings": 0,
    "recent_orders": 0,
    "total_sales": 0,
    "shop_rating": 0.0,
    "shop_currency": "USD",
    "last_order_date": "None",
    "last_listing_update": "None",
    "shop_status": "Unknown",
    "total_favorites": 0,
}