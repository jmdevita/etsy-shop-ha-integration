"""Application credentials for the Etsy integration."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .const import DOMAIN


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return Etsy's PKCE-enabled OAuth2 implementation."""
    from .config_flow import EtsyOAuth2Implementation

    return EtsyOAuth2Implementation(
        hass,
        DOMAIN,
        credential.client_id,
        credential.client_secret,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "etsy_developers": "[Etsy Developers](https://developers.etsy.com/documentation/getting_started)",
    }
