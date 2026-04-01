"""Application credentials for the Etsy integration."""

from homeassistant.core import HomeAssistant


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "etsy_developers": "[Etsy Developers](https://developers.etsy.com/documentation/getting_started)",
    }
