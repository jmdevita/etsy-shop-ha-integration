"""Etsy Shop Services."""

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .utils import build_transaction_detail

_LOGGER = logging.getLogger(__name__)

REFRESH_DATA_SCHEMA = vol.Schema({})

GET_SHOP_STATS_SCHEMA = vol.Schema(
    {
        vol.Optional("include_listings", default=True): cv.boolean,
        vol.Optional("include_transactions", default=True): cv.boolean,
    }
)

FIRE_TEST_EVENT_SCHEMA = vol.Schema(
    {
        vol.Optional("event_type", default="new_order"): vol.In(
            ["new_order", "new_review", "low_stock"]
        ),
    }
)


async def async_register_services(hass: HomeAssistant):
    """Register Etsy services."""

    async def async_refresh_data(call: ServiceCall):
        """Manually refresh shop data from Etsy API."""
        _LOGGER.info("Manually refreshing Etsy shop data")

        # Find all Etsy coordinators and refresh them
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if "coordinator" in entry_data:
                coordinator = entry_data["coordinator"]
                await coordinator.async_request_refresh()
                _LOGGER.info("Refreshed data for entry %s", entry_id)

    async def async_get_shop_stats(call: ServiceCall):
        """Get current shop statistics."""
        include_listings = call.data["include_listings"]
        include_transactions = call.data["include_transactions"]

        _LOGGER.info("Getting shop stats: listings=%s, transactions=%s", include_listings, include_transactions)

        # Get the first coordinator's data
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if "coordinator" in entry_data:
                coordinator = entry_data["coordinator"]
                await coordinator.async_request_refresh()

                data = coordinator.data
                if data:
                    stats = {
                        "shop_name": data.get("shop", {}).get("shop_name", "Unknown"),
                        "listings_count": data.get("listings_count", 0),
                        "transactions_count": data.get("transactions_count", 0),
                        "last_updated": data.get("last_updated"),
                    }

                    if include_listings and "listings" in data:
                        stats["recent_listings"] = data["listings"][:5]

                    if include_transactions and "transactions" in data:
                        stats["recent_transactions"] = [
                            build_transaction_detail(t)
                            for t in data["transactions"][:5]
                        ]

                    _LOGGER.debug("Shop stats retrieved: %s", stats)
                    return stats
                break

        _LOGGER.warning("No shop data available")
        return {}

    async def async_fire_test_event(call: ServiceCall):
        """Fire a test event for automation testing."""
        event_type = call.data["event_type"]

        # Find coordinator and device for event data
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if "coordinator" not in entry_data:
                continue

            coordinator = entry_data["coordinator"]
            config_entry = coordinator.config_entry

            device_registry = dr.async_get(hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, config_entry.entry_id)}
            )
            device_id = device.id if device else None

            data = coordinator.data or {}
            shop = data.get("shop", {})
            shop_name = shop.get("shop_name", "Test Shop")

            event_data = None

            if event_type == "new_order":
                # Use most recent real transaction if available, otherwise sample data
                transactions = data.get("transactions", [])
                if transactions:
                    order_detail = build_transaction_detail(transactions[0])
                else:
                    order_detail = {
                        "transaction_id": "0000000000",
                        "title": "Test Listing - Sample Order",
                        "listing_id": "0000000000",
                        "buyer_user_id": "0000000000",
                        "quantity": 1,
                        "price_amount": 25.00,
                        "price_currency": "USD",
                        "variations": [
                            {"property": "Color", "value": "Blue"},
                        ],
                        "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "updated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                event_data = {
                    "device_id": device_id,
                    "shop_name": shop_name,
                    "new_orders": 1,
                    "orders": [order_detail],
                    "receipts": [
                        {
                            "receipt_id": order_detail.get("receipt_id", "0000000000"),
                            "buyer_user_id": order_detail.get("buyer_user_id", "0000000000"),
                            "item_count": 1,
                            "items": [order_detail],
                        }
                    ],
                }

            elif event_type == "new_review":
                event_data = {
                    "device_id": device_id,
                    "shop_name": shop_name,
                    "new_reviews": 1,
                    "average_rating": shop.get("review_average", 5.0),
                }

            elif event_type == "low_stock":
                # Use first listing if available, otherwise sample
                listings = data.get("listings", [])
                if listings:
                    listing = listings[0]
                    event_data = {
                        "device_id": device_id,
                        "shop_name": shop_name,
                        "listing_id": listing.get("listing_id"),
                        "listing_title": listing.get("title"),
                        "quantity": 2,
                        "threshold": config_entry.options.get("stock_threshold", 5),
                    }
                else:
                    event_data = {
                        "device_id": device_id,
                        "shop_name": shop_name,
                        "listing_id": "0000000000",
                        "listing_title": "Test Listing - Low Stock",
                        "quantity": 2,
                        "threshold": 5,
                    }

            if event_data is not None:
                hass.bus.async_fire(f"{DOMAIN}_{event_type}", event_data)
                _LOGGER.info("Fired test %s event for shop %s", event_type, shop_name)
            else:
                _LOGGER.error("Unknown event type: %s", event_type)
            return

        _LOGGER.warning("No Etsy shop configured, cannot fire test event")

    # Register services
    hass.services.async_register(
        DOMAIN,
        "refresh_data",
        async_refresh_data,
        schema=REFRESH_DATA_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "get_shop_stats",
        async_get_shop_stats,
        schema=GET_SHOP_STATS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        "fire_test_event",
        async_fire_test_event,
        schema=FIRE_TEST_EVENT_SCHEMA,
    )

    _LOGGER.info("Etsy services registered successfully")


async def async_unregister_services(hass: HomeAssistant):
    """Unregister Etsy services."""
    hass.services.async_remove(DOMAIN, "refresh_data")
    hass.services.async_remove(DOMAIN, "get_shop_stats")
    hass.services.async_remove(DOMAIN, "fire_test_event")

    _LOGGER.info("Etsy services unregistered")
