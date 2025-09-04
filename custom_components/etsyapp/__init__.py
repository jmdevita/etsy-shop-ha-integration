"""Integration for Etsy Shop monitoring."""

import logging
from typing import Any
from urllib.parse import quote

from homeassistant.const import Platform, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, CONNECTION_MODE_DIRECT, CONF_CONNECTION_MODE
from .coordinator import EtsyConfigEntry, EtsyUpdateCoordinator
from .services import async_register_services

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration."""
    _LOGGER.debug("Setting up the Etsy Shop integration")

    # Store integration data in hass.data
    hass.data[DOMAIN] = {}
    await async_register_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: EtsyConfigEntry) -> bool:
    """Set up the integration based on a config entry."""
    _LOGGER.debug("Setting up Etsy Shop integration for entry %s", entry.entry_id)

    # Check if the entry is already set up
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        raise ValueError(
            f"Config entry {entry.title} ({entry.entry_id}) for {DOMAIN} has already been setup!"
        )
    
    # Register OAuth implementation if this is direct mode
    connection_mode = entry.data.get(CONF_CONNECTION_MODE, CONNECTION_MODE_DIRECT)
    if connection_mode == CONNECTION_MODE_DIRECT:
        # Check if we have OAuth credentials stored
        client_id = entry.data.get("auth_implementation_client_id")
        # Try to get client_secret from entry data (it might be stored during config flow)
        client_secret = entry.data.get("client_secret")
        
        if client_id and client_secret:
            # Import the OAuth implementation class
            from .config_flow import EtsyOAuth2Implementation
            
            # Create and register the OAuth implementation
            implementation = EtsyOAuth2Implementation(
                hass,
                DOMAIN,
                client_id,
                client_secret,
            )
            
            # Register it for this domain
            try:
                config_entry_oauth2_flow.async_register_implementation(
                    hass,
                    DOMAIN,
                    implementation
                )
                _LOGGER.debug("OAuth implementation registered for Etsy integration")
            except ValueError as e:
                # Implementation might already be registered
                _LOGGER.debug("OAuth implementation already registered or error: %s", e)
        else:
            _LOGGER.warning("OAuth credentials not found in config entry, token refresh may not work")

    # Setup the coordinator
    coordinator = EtsyUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}
    
    # Create device registry entry
    device_registry = dr.async_get(hass)
    shop_name = entry.data.get("shop_name", "Etsy Shop")
    shop_id = entry.data.get("shop_id", "unknown")
    
    # URL encode the shop name for the configuration URL
    url_safe_shop_name = quote(shop_name, safe='')
    
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Etsy",
        model="Etsy Shop",
        name=shop_name,
        sw_version="1.0",
        configuration_url=f"https://www.etsy.com/shop/{url_safe_shop_name}",
    )

    # Forward entry setups only if not already forwarded
    if "platforms" not in hass.data[DOMAIN][entry.entry_id]:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        hass.data[DOMAIN][entry.entry_id]["platforms"] = PLATFORMS

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    await cleanup_old_device(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EtsyConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Etsy Shop integration")

    # Unload platforms
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        platforms = hass.data[DOMAIN][entry.entry_id].get("platforms", [])
        unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)

        # Clean up resources
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)
            if not hass.data[DOMAIN]:  # If no entries remain, clean up DOMAIN
                hass.data.pop(DOMAIN)

        return unload_ok

    return False


async def async_update_entry(hass: HomeAssistant, config_entry: EtsyConfigEntry):
    """Reload Etsy Shop component when options changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def cleanup_old_device(hass: HomeAssistant) -> None:
    """Cleanup device without proper device identifier."""
    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN,)})
    if device:
        _LOGGER.debug("Removing improper device %s", device.name)
        device_reg.async_remove_device(device.id)
