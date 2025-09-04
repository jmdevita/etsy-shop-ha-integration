"""Etsy Shop Services."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REFRESH_DATA_SCHEMA = vol.Schema({})

GET_SHOP_STATS_SCHEMA = vol.Schema(
    {
        vol.Optional("include_listings", default=True): cv.boolean,
        vol.Optional("include_transactions", default=True): cv.boolean,
    }
)


async def async_register_services(hass: HomeAssistant):
    """Register Etsy services."""

    session = async_get_clientsession(hass)

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
                        stats["recent_transactions"] = data["transactions"][:5]
                    
                    _LOGGER.debug("Shop stats retrieved: %s", stats)
                    return stats
                break
        
        _LOGGER.warning("No shop data available")
        return {}

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
    )

    _LOGGER.info("Etsy services registered successfully")


async def async_unregister_services(hass: HomeAssistant):
    """Unregister Etsy services."""
    hass.services.async_remove(DOMAIN, "refresh_data")
    hass.services.async_remove(DOMAIN, "get_shop_stats")
    
    _LOGGER.info("Etsy services unregistered")