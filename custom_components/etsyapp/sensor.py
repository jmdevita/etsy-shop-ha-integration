"""Integration for Etsy shop monitoring sensors."""

from collections import defaultdict
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
    ETSY_ORDER_STATUSES,
    ETSY_LISTING_STATES,
    EtsyShop,
    EMPTY_SHOP,
    EMPTY_ATTRIBUTES,
)
from .coordinator import EtsyConfigEntry, EtsyUpdateCoordinator
from .utils import build_transaction_detail

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EtsyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Etsy sensor platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            EtsyShopInfo(coordinator),
            EtsyActiveListings(coordinator),
            EtsyRecentOrders(coordinator),
            EtsyLastOrder(coordinator),
            EtsyShopStats(coordinator),
        ],
        update_before_add=True,
    )


class EtsyShopInfo(CoordinatorEntity, SensorEntity):
    """Representation of sensor that shows basic Etsy shop information."""

    def __init__(self, coordinator: EtsyUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hass_custom_attributes = {}
        self._attr_name = "Etsy Shop Info"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_shop_info"
        self._globalid = "etsy_shop_info"
        self._attr_icon = "mdi:store"
        self._attr_state = None
        # Associate with device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
        }

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        etsy_data = self.coordinator.data

        if not etsy_data or not etsy_data.get("shop"):
            self._attr_state = "No shop data"
            self._attr_icon = "mdi:store-off"
            self._hass_custom_attributes = EMPTY_ATTRIBUTES
        else:
            shop = etsy_data["shop"]
            self._attr_state = shop.get("shop_name", "Unknown Shop")
            self._attr_icon = "mdi:store"

            # Format creation date from timestamp
            creation_date = None
            if shop.get("creation_timestamp"):
                try:
                    # Convert Unix timestamp to readable date
                    timestamp = int(shop["creation_timestamp"])
                    creation_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError, OSError) as e:
                    _LOGGER.debug("Failed to convert creation_timestamp %s: %s", shop.get("creation_timestamp"), e)
                    creation_date = str(shop.get("creation_timestamp"))

            self._hass_custom_attributes = {
                "shop_id": str(shop.get("shop_id", "")),  # Keep as string without formatting
                "shop_name": shop.get("shop_name"),
                "currency_code": shop.get("currency_code", "USD"),
                "creation_date": creation_date or shop.get("create_date"),
                "title": shop.get("title"),
                "announcement": shop.get("announcement"),
                "sale_message": shop.get("sale_message"),
                "digital_sale_message": shop.get("digital_sale_message"),
                "is_vacation": shop.get("is_vacation", False),
                "vacation_message": shop.get("vacation_message"),
                "listing_active_count": shop.get("listing_active_count", 0),
                "transaction_sold_count": shop.get("transaction_sold_count", 0),
                "review_average": shop.get("review_average", 0),
                "review_count": shop.get("review_count", 0),
                "shop_url": shop.get("url"),
                "last_updated": etsy_data.get("last_updated"),
            }

        self.async_write_ha_state()


class EtsyActiveListings(CoordinatorEntity, SensorEntity):
    """Representation of sensor that shows active listings count and details."""

    def __init__(self, coordinator: EtsyUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hass_custom_attributes = {}
        self._attr_name = "Etsy Active Listings"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_active_listings"
        self._globalid = "etsy_active_listings"
        self._attr_icon = "mdi:format-list-bulleted"
        self._attr_state = None
        # Get display limit from options
        self._display_limit = coordinator.config_entry.options.get("listings_display_limit", 5)
        # Associate with device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
        }

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        etsy_data = self.coordinator.data

        if not etsy_data:
            self._attr_state = 0
            self._attr_icon = "mdi:format-list-bulleted-off"
            self._hass_custom_attributes = {"active_listings": []}
        else:
            listings_count = etsy_data.get("listings_count", 0)
            listings = etsy_data.get("listings", [])

            self._attr_state = listings_count

            # Set icon based on listing count
            if listings_count == 0:
                self._attr_icon = "mdi:format-list-bulleted-off"
            elif listings_count < 10:
                self._attr_icon = f"mdi:numeric-{listings_count}-circle"
            else:
                self._attr_icon = "mdi:numeric-9-plus-circle"

            # Create summary of listings
            # API fetches up to 10 listings, display limit is configurable
            # Update display limit from options on each update
            self._display_limit = self.coordinator.config_entry.options.get("listings_display_limit", 5)
            listings_summary = []
            for listing in listings[:self._display_limit]:  # Show configured number of listings
                summary = {
                    "listing_id": str(listing.get("listing_id", "")),  # Keep as string
                    "title": listing.get("title"),
                    "state": listing.get("state"),
                    "price": listing.get("price"),
                    "currency_code": listing.get("currency_code"),
                    "quantity": listing.get("quantity"),
                    "views": listing.get("views"),
                    "num_favorers": listing.get("num_favorers"),
                }
                listings_summary.append(summary)

            self._hass_custom_attributes = {
                "listings_count": listings_count,
                "recent_listings": listings_summary,
                "total_views": sum(listing.get("views", 0) for listing in listings),
                "total_favorites": sum(listing.get("num_favorers", 0) for listing in listings),
            }

        self.async_write_ha_state()


class EtsyRecentOrders(CoordinatorEntity, SensorEntity):
    """Representation of sensor that shows recent transactions/orders."""

    def __init__(self, coordinator: EtsyUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hass_custom_attributes = {}
        self._attr_name = "Etsy Recent Orders"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_recent_orders"
        self._globalid = "etsy_recent_orders"
        self._attr_icon = "mdi:shopping"
        self._attr_state = None
        # Get display limit from options
        self._display_limit = coordinator.config_entry.options.get("transactions_display_limit", 10)
        # Associate with device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
        }

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        etsy_data = self.coordinator.data

        if not etsy_data:
            self._attr_state = 0
            self._attr_icon = "mdi:shopping-off"
            self._hass_custom_attributes = {"recent_transactions": []}
        else:
            transactions_count = etsy_data.get("transactions_count", 0)
            transactions = etsy_data.get("transactions", [])

            self._attr_state = transactions_count

            # Set icon based on transaction count
            if transactions_count == 0:
                self._attr_icon = "mdi:shopping-off"
            elif transactions_count < 10:
                self._attr_icon = f"mdi:numeric-{transactions_count}-circle"
            else:
                self._attr_icon = "mdi:numeric-9-plus-circle"

            # Create summary of recent transactions
            # API fetches up to 10 transactions, display limit is configurable
            # Update display limit from options on each update
            self._display_limit = self.coordinator.config_entry.options.get("transactions_display_limit", 10)
            transactions_summary = []
            total_revenue = 0

            for transaction in transactions[:self._display_limit]:
                summary = build_transaction_detail(transaction)
                total_revenue += summary["price_amount"] * (summary.get("quantity") or 1)
                transactions_summary.append(summary)

            self._hass_custom_attributes = {
                "transactions_count": transactions_count,
                "recent_transactions": transactions_summary,
                "total_recent_revenue": round(total_revenue, 2),
                "currency_code": transactions_summary[0]["price_currency"] if transactions_summary else "USD",
            }

        self.async_write_ha_state()


class EtsyLastOrder(CoordinatorEntity, SensorEntity):
    """Representation of sensor that shows the most recent order with per-SKU breakdown."""

    def __init__(self, coordinator: EtsyUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hass_custom_attributes = {}
        self._attr_name = "Etsy Last Order"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_last_order"
        self._globalid = "etsy_last_order"
        self._attr_icon = "mdi:cart"
        self._attr_state = None
        # Associate with device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
        }

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        etsy_data = self.coordinator.data

        if not etsy_data:
            self._attr_state = 0
            self._attr_icon = "mdi:cart-off"
            self._hass_custom_attributes = {}
            self.async_write_ha_state()
            return

        transactions = etsy_data.get("transactions", [])
        if not transactions:
            self._attr_state = 0
            self._attr_icon = "mdi:cart-off"
            self._hass_custom_attributes = {}
            self.async_write_ha_state()
            return

        # Group transactions by receipt_id to identify items from the same order
        grouped = defaultdict(list)
        for txn in transactions:
            receipt_id = txn.get("receipt_id")
            if receipt_id:
                grouped[str(receipt_id)].append(txn)
            else:
                # Fallback: treat each transaction as its own order
                grouped[str(txn.get("transaction_id", ""))].append(txn)

        # Find the most recent order group by max created_timestamp
        most_recent_receipt = None
        most_recent_timestamp = 0
        for receipt_id, txns in grouped.items():
            group_timestamp = max(
                t.get("created_timestamp", 0) for t in txns
            )
            if group_timestamp > most_recent_timestamp:
                most_recent_timestamp = group_timestamp
                most_recent_receipt = receipt_id

        if not most_recent_receipt:
            self._attr_state = 0
            self._attr_icon = "mdi:cart-off"
            self._hass_custom_attributes = {}
            self.async_write_ha_state()
            return

        order_transactions = grouped[most_recent_receipt]

        # Build per-item details
        items = []
        order_total = 0
        total_quantity = 0
        for txn in order_transactions:
            detail = build_transaction_detail(txn)
            items.append(detail)
            qty = detail.get("quantity") or 1
            order_total += detail["price_amount"] * qty
            total_quantity += qty

        # Get order-level info from the first transaction
        first_item = items[0]
        order_date = min(
            (item["created_date"] for item in items if item.get("created_date")),
            default=None,
        )

        self._attr_state = total_quantity
        self._attr_icon = "mdi:cart"

        self._hass_custom_attributes = {
            "receipt_id": most_recent_receipt,
            "buyer_user_id": first_item.get("buyer_user_id"),
            "order_total": round(order_total, 2),
            "currency_code": first_item.get("price_currency", "USD"),
            "order_date": order_date,
            "item_count": len(items),
            "items": items,
        }

        self.async_write_ha_state()


class EtsyShopStats(CoordinatorEntity, SensorEntity):
    """Representation of sensor that shows overall shop statistics."""

    def __init__(self, coordinator: EtsyUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hass_custom_attributes = {}
        self._attr_name = "Etsy Shop Statistics"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_shop_stats"
        self._globalid = "etsy_shop_stats"
        self._attr_icon = "mdi:chart-line"
        self._attr_state = None
        # Associate with device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
        }

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        etsy_data = self.coordinator.data

        if not etsy_data:
            self._attr_state = "No data"
            self._attr_icon = "mdi:chart-line-off"
            self._hass_custom_attributes = EMPTY_ATTRIBUTES
        else:
            shop = etsy_data.get("shop", {})
            listings_count = etsy_data.get("listings_count", 0)
            transactions_count = etsy_data.get("transactions_count", 0)

            # Use shop transaction sold count as the state
            sale_count = shop.get("transaction_sold_count", 0)
            self._attr_state = f"{sale_count} total sales"

            # Calculate some basic stats
            listings = etsy_data.get("listings", [])
            transactions = etsy_data.get("transactions", [])

            total_views = sum(listing.get("views", 0) for listing in listings)
            total_favorites = sum(listing.get("num_favorers", 0) for listing in listings)

            # Calculate recent revenue
            recent_revenue = 0
            for transaction in transactions:
                price = transaction.get("price", {})
                if price.get("amount"):
                    qty = transaction.get("quantity") or 1
                    recent_revenue += float(price["amount"]) / 100 * qty

            self._hass_custom_attributes = {
                "total_sales": sale_count,
                "active_listings": listings_count,
                "recent_transactions": transactions_count,
                "total_views": total_views,
                "total_favorites": total_favorites,
                "recent_revenue": round(recent_revenue, 2),
                "shop_currency": shop.get("currency_code", "USD"),
                "average_rating": shop.get("review_average", 0.0),
                "total_reviews": shop.get("review_count", 0),
                "last_updated": etsy_data.get("last_updated"),
            }

        self.async_write_ha_state()