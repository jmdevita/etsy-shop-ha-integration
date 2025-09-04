"""Device triggers for Etsy Shop integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define the trigger types we support
TRIGGER_TYPES = {
    "new_order",
    "low_stock",
    "new_review",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Etsy Shop devices.
    
    This is called by the automation UI to show available triggers.
    """
    triggers = []

    # Get the device from the registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    
    if device and device.model == "Etsy Shop":
        # Add all our trigger types
        base_trigger = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
        }
        
        triggers = [
            {
                **base_trigger,
                CONF_TYPE: "new_order",
                "metadata": {"description": "Triggers when a new order is received"},
            },
            {
                **base_trigger,
                CONF_TYPE: "low_stock",
                "metadata": {"description": "Triggers when a listing has low stock"},
            },
            {
                **base_trigger,
                CONF_TYPE: "new_review",
                "metadata": {"description": "Triggers when a new review is posted"},
            },
        ]
    
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger to fire when an Etsy Shop event occurs.
    
    This is called when the automation is set up.
    """
    device_id = config[CONF_DEVICE_ID]
    trigger_type = config[CONF_TYPE]
    
    # Build the event type based on our domain and trigger type
    event_type = f"{DOMAIN}_{trigger_type}"
    
    # Use Home Assistant's event trigger to listen for our custom events
    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: event_type,
        event_trigger.CONF_EVENT_DATA: {
            CONF_DEVICE_ID: device_id,
        },
    }
    
    # Attach the event trigger
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities.
    
    This allows adding extra fields to the trigger configuration.
    For example, we could add a threshold for low_stock triggers.
    """
    trigger_type = config[CONF_TYPE]
    
    if trigger_type == "low_stock":
        # Allow user to set stock threshold
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional("stock_threshold", default=5): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=20)
                    ),
                }
            )
        }
    
    return {}