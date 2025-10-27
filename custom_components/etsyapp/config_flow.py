"""Config flow for Etsy Shop integration with OAuth2 support."""

import logging
from typing import Any

from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2ImplementationWithPkce
from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN, 
    ETSY_API_BASE,
    CONNECTION_MODE_DIRECT,
    CONNECTION_MODE_PROXY,
    CONF_CONNECTION_MODE,
    CONF_PROXY_URL,
    CONF_PROXY_API_KEY,
    CONF_HMAC_SECRET,
)

_LOGGER = logging.getLogger(__name__)


class EtsyOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Local OAuth2 implementation for Etsy with PKCE support."""

    def __init__(self, hass, domain, client_id, client_secret) -> None:
        """Initialize Etsy OAuth2 implementation."""
        super().__init__(
            hass,
            domain=domain,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://www.etsy.com/oauth/connect",
            token_url="https://api.etsy.com/v3/public/oauth/token",
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Etsy"

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        # Get parent's PKCE parameters
        data = super().extra_authorize_data
        # Add Etsy-specific parameters
        data.update({
            "response_type": "code",
            "scope": " ".join(["transactions_r", "listings_r", "shops_r"]),
        })
        return data


class EtsyFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Etsy OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 1
    
    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return EtsyOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self._shop_id: str | None = None
        self._shop_name: str | None = None
        self.etsy_credentials: dict[str, str] | None = None
        self.connection_mode: str | None = None
        self.proxy_config: dict[str, Any] | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_connection_mode(user_input)
    
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        entry = self._get_reconfigure_entry()

        # Get the connection mode from the existing entry
        connection_mode = entry.data.get(CONF_CONNECTION_MODE, CONNECTION_MODE_DIRECT)

        if user_input is not None:
            # Update the config entry with new credentials based on connection mode
            new_data = dict(entry.data)

            if connection_mode == CONNECTION_MODE_PROXY:
                # Update proxy credentials
                new_data[CONF_PROXY_API_KEY] = user_input[CONF_PROXY_API_KEY]
                new_data[CONF_HMAC_SECRET] = user_input[CONF_HMAC_SECRET]

                # Optionally update proxy URL if provided
                if CONF_PROXY_URL in user_input:
                    proxy_url = user_input[CONF_PROXY_URL].rstrip('/')
                    if proxy_url.endswith('/api/v1'):
                        proxy_url = proxy_url[:-7]
                    new_data[CONF_PROXY_URL] = proxy_url
            else:
                # Update direct mode credentials
                new_data["auth_implementation_client_id"] = user_input[CONF_CLIENT_ID]
                new_data["client_secret"] = user_input[CONF_CLIENT_SECRET]

            # Update and reload the entry
            return self.async_update_reload_and_abort(
                entry,
                data=new_data,
                reason="reconfigure_successful"
            )

        # Build form based on connection mode
        if connection_mode == CONNECTION_MODE_PROXY:
            # Pre-fill current proxy values
            proxy_url = entry.data.get(CONF_PROXY_URL, "")
            proxy_api_key = entry.data.get(CONF_PROXY_API_KEY, "")

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({
                    vol.Optional(CONF_PROXY_URL, default=proxy_url): cv.string,
                    vol.Required(CONF_PROXY_API_KEY, default=proxy_api_key): cv.string,
                    vol.Required(CONF_HMAC_SECRET): cv.string,
                }),
                description_placeholders={
                    "shop_name": entry.data.get("shop_name", "your shop"),
                }
            )
        else:
            # Pre-fill current direct mode values
            client_id = entry.data.get("auth_implementation_client_id", "")

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({
                    vol.Required(CONF_CLIENT_ID, default=client_id): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                }),
                description_placeholders={
                    "shop_name": entry.data.get("shop_name", "your shop"),
                }
            )
    
    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle re-authentication for missing credentials."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        
        # Check if user_input has the required fields (not just if it exists)
        if user_input is not None and CONF_CLIENT_SECRET in user_input:
            # Store the new credentials
            new_data = dict(self.reauth_entry.data)
            new_data["client_secret"] = user_input[CONF_CLIENT_SECRET]
            
            # Also update the auth_implementation_client_id if provided
            if CONF_CLIENT_ID in user_input:
                new_data["auth_implementation_client_id"] = user_input[CONF_CLIENT_ID]
            
            # Update the config entry
            self.hass.config_entries.async_update_entry(
                self.reauth_entry,
                data=new_data
            )
            
            # Reload the integration
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            
            return self.async_abort(reason="reauth_successful")
        
        # Pre-fill client_id if available
        client_id = self.reauth_entry.data.get("auth_implementation_client_id", "")
        
        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID, description={"suggested_value": client_id}): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }),
            description_placeholders={
                "instructions": "Your Etsy credentials are missing or incomplete. Please re-enter them from your Etsy Developer Dashboard."
            }
        )
    
    async def async_step_connection_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle connection mode selection."""
        if user_input is not None:
            self.connection_mode = user_input[CONF_CONNECTION_MODE]

            if self.connection_mode == CONNECTION_MODE_PROXY:
                # Proceed to proxy configuration
                return await self.async_step_proxy_config()
            else:
                return await self.async_step_direct_credentials()
        
        return self.async_show_form(
            step_id="connection_mode",
            data_schema=vol.Schema({
                vol.Required(CONF_CONNECTION_MODE, default=CONNECTION_MODE_DIRECT): vol.In({
                    CONNECTION_MODE_DIRECT: "Direct Etsy API (requires dev account)",
                    CONNECTION_MODE_PROXY: "Proxy Service (Beta)"
                })
            }),
            description_placeholders={
                "direct_desc": "Connect directly to Etsy API using your developer credentials",
                "proxy_desc": "Use the proxy service to connect without an Etsy developer account (Beta)"
            }
        )
    
    async def async_step_direct_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle direct API credentials input."""
        if user_input is not None:
            # Store credentials for later use
            self.etsy_credentials = {
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
            }
            
            # Create and register the OAuth2 implementation
            from homeassistant.helpers import config_entry_oauth2_flow
            
            # Create implementation with user's credentials (using our PKCE-enabled implementation)
            implementation = EtsyOAuth2Implementation(
                self.hass,
                DOMAIN,
                user_input[CONF_CLIENT_ID],
                user_input[CONF_CLIENT_SECRET],
            )
            
            # Register it as an available implementation
            config_entry_oauth2_flow.async_register_implementation(
                self.hass,
                DOMAIN,
                implementation
            )
            
            # Set this as the active implementation for this flow
            self.flow_impl = implementation
            
            # Continue with OAuth flow
            return await self.async_step_pick_implementation(user_input={"implementation": DOMAIN})
        
        return self.async_show_form(
            step_id="direct_credentials",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID, description={"suggested_value": "Your Etsy App Keystring"}): cv.string,
                vol.Required(CONF_CLIENT_SECRET, description={"suggested_value": "Your Etsy Shared Secret"}): cv.string,
            }),
            description_placeholders={
                "instructions": "Enter your Etsy API credentials from the Etsy Developer Dashboard"
            }
        )
    
    async def async_step_proxy_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle proxy configuration."""
        errors = {}
        
        if user_input is not None:
            # Validate proxy connection with HMAC if provided
            valid = await self._validate_proxy_connection(
                user_input[CONF_PROXY_URL],
                user_input[CONF_PROXY_API_KEY],
                user_input.get(CONF_HMAC_SECRET)
            )
            
            if valid:
                # Clean up the URL before storing
                proxy_url = user_input[CONF_PROXY_URL].rstrip('/')
                if proxy_url.endswith('/api/v1'):
                    proxy_url = proxy_url[:-7]  # Remove '/api/v1'
                    
                # Store proxy config and proceed to shop selection
                self.proxy_config = {
                    CONF_CONNECTION_MODE: CONNECTION_MODE_PROXY,
                    CONF_PROXY_URL: proxy_url,
                    CONF_PROXY_API_KEY: user_input[CONF_PROXY_API_KEY],
                    CONF_HMAC_SECRET: user_input[CONF_HMAC_SECRET],
                }
                return await self.async_step_proxy_shop_selection()
            else:
                errors["base"] = "invalid_proxy"
        
        return self.async_show_form(
            step_id="proxy_config",
            data_schema=vol.Schema({
                vol.Required(CONF_PROXY_URL, default="http://localhost:8000"): cv.string,
                vol.Required(CONF_PROXY_API_KEY): cv.string,
                vol.Required(CONF_HMAC_SECRET): cv.string,
            }),
            errors=errors,
            description_placeholders={
                "instructions": "Enter your proxy service URL, API key, and HMAC secret for secure communication"
            }
        )
    
    async def _validate_proxy_connection(
        self, proxy_url: str, api_key: str, hmac_secret: str | None = None
    ) -> bool:
        """Validate proxy connection with HMAC authentication if secret provided."""
        try:
            session = async_get_clientsession(self.hass)
            
            # Clean up the URL - remove trailing slash and /api/v1 if present
            proxy_url = proxy_url.rstrip('/')
            if proxy_url.endswith('/api/v1'):
                proxy_url = proxy_url[:-7]  # Remove '/api/v1'
            
            path = "/health"
            
            if hmac_secret:
                # Use HMAC authentication
                from .hmac_client import HMACClient
                hmac_client = HMACClient(api_key, hmac_secret)
                headers = hmac_client.get_headers_with_signature(
                    method="GET",
                    path=path,
                    api_key=api_key
                )
            else:
                # Fallback to simple bearer token (will fail on secure proxy)
                headers = {"Authorization": f"Bearer {api_key}"}
            
            # Test the health endpoint
            response = await session.get(
                f"{proxy_url}{path}",
                headers=headers,
                timeout=10
            )
            
            return response.status == 200
        except Exception as e:
            _LOGGER.error(f"Proxy validation failed: {e}")
            return False

    async def async_step_shop_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle shop selection step."""
        if user_input is not None:
            self._shop_id = user_input["shop_id"]
            
            # Validate shop access
            if await self._validate_shop_access(self._shop_id):
                return await self._create_config_entry()
            else:
                return self.async_show_form(
                    step_id="shop_selection",
                    data_schema=vol.Schema({
                        vol.Required("shop_id"): cv.string,
                    }),
                    errors={"shop_id": "shop_access_denied"},
                )

        # Get available shops from API
        shops = await self._get_user_shops()
        
        if not shops:
            return self.async_abort(reason="no_shops_found")
        
        if len(shops) == 1:
            # Only one shop, use it automatically
            self._shop_id = str(shops[0]["shop_id"])
            self._shop_name = shops[0]["shop_name"]
            return await self._create_config_entry()

        # Multiple shops, let user choose
        shop_options = {str(shop["shop_id"]): shop["shop_name"] for shop in shops}
        
        return self.async_show_form(
            step_id="shop_selection",
            data_schema=vol.Schema({
                vol.Required("shop_id"): vol.In(shop_options),
            }),
            description_placeholders={
                "num_shops": str(len(shops)),
            },
        )

    async def async_step_proxy_shop_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle shop selection for proxy mode."""
        if user_input is not None:
            shop_id = user_input["shop_id"]
            
            # Get shop name from our stored shop options
            shops = await self._get_proxy_shops()
            shop_name = next((shop.get("shop_name", shop.get("title", f"Shop {shop_id}")) for shop in shops if str(shop["shop_id"]) == shop_id), f"Shop {shop_id}")
            
            # Create entry with proxy config and selected shop
            return self.async_create_entry(
                title=f"{shop_name} ({shop_id}) - Proxy",
                data={
                    **self.proxy_config,
                    "shop_id": shop_id,
                    "shop_name": shop_name,
                }
            )
        
        # Get available shops from proxy
        shops = await self._get_proxy_shops()
        
        if not shops:
            return self.async_abort(reason="no_shops_found")
        
        if len(shops) == 1:
            # Only one shop, use it automatically
            shop_name = shops[0].get("shop_name", shops[0].get("title", f"Shop {shops[0]['shop_id']}"))
            shop_id = str(shops[0]["shop_id"])
            return self.async_create_entry(
                title=f"{shop_name} ({shop_id}) - Proxy",
                data={
                    **self.proxy_config,
                    "shop_id": shop_id,
                    "shop_name": shop_name,
                }
            )
        
        # Multiple shops, let user choose
        shop_options = {str(shop["shop_id"]): shop.get("shop_name", shop.get("title", f"Shop {shop['shop_id']}")) for shop in shops}
        
        return self.async_show_form(
            step_id="proxy_shop_selection",
            data_schema=vol.Schema({
                vol.Required("shop_id"): vol.In(shop_options),
            }),
            description_placeholders={
                "num_shops": str(len(shops)),
            },
        )
    
    async def _get_proxy_shops(self) -> list[dict[str, Any]]:
        """Get shops from proxy service."""
        try:
            session = async_get_clientsession(self.hass)
            
            path = "/api/v1/shops"
            hmac_secret = self.proxy_config.get(CONF_HMAC_SECRET)
            
            if hmac_secret:
                # Use HMAC authentication
                from .hmac_client import HMACClient
                hmac_client = HMACClient(self.proxy_config[CONF_PROXY_API_KEY], hmac_secret)
                headers = hmac_client.get_headers_with_signature(
                    method="GET",
                    path=path,
                    api_key=self.proxy_config[CONF_PROXY_API_KEY]
                )
            else:
                # This will fail on secure proxy
                headers = {"Authorization": f"Bearer {self.proxy_config[CONF_PROXY_API_KEY]}"}
            
            response = await session.get(
                f"{self.proxy_config[CONF_PROXY_URL]}{path}",
                headers=headers,
                timeout=10
            )
            
            if response.status == 200:
                return await response.json()
            else:
                _LOGGER.error(f"Failed to get shops from proxy: {response.status}")
                return []
                
        except Exception as e:
            _LOGGER.error(f"Error getting shops from proxy: {e}")
            return []

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for Etsy Shop."""
        # Store OAuth data and get user's shops
        self.oauth_data = data
        return await self.async_step_shop_selection()

    async def _get_user_shops(self) -> list[dict[str, Any]]:
        """Get list of shops for the authenticated user."""
        try:
            session = async_get_clientsession(self.hass)
            
            # Extract user_id from access token (format: user_id.scope.token)
            access_token = self.oauth_data.get("token", {}).get("access_token", "")
            _LOGGER.debug("Extracting user_id from OAuth token")
            
            if '.' in access_token:
                user_id = access_token.split('.')[0]
                _LOGGER.debug("Extracted user_id %s from access token", user_id)
            else:
                _LOGGER.error(f"Unable to extract user_id from access token. Token format: {access_token[:20]}...")
                return []
            
            # Get client_id from various sources
            client_id = None
            if hasattr(self, 'flow_impl') and self.flow_impl:
                client_id = self.flow_impl.client_id
            elif self.etsy_credentials:
                client_id = self.etsy_credentials.get(CONF_CLIENT_ID)
            else:
                # Try to get from registered implementations
                from homeassistant.helpers import config_entry_oauth2_flow
                implementations = await config_entry_oauth2_flow.async_get_implementations(
                    self.hass, DOMAIN
                )
                if implementations:
                    # Get the first implementation
                    impl = next(iter(implementations.values()))
                    client_id = impl.client_id
            
            if not client_id:
                _LOGGER.error("Unable to get client_id for API request")
                return []
                
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": client_id,
                "Authorization": f"Bearer {access_token}",
            }
            
            # Get user's shops directly using extracted user_id
            shops_url = f"{ETSY_API_BASE}/users/{user_id}/shops"
            _LOGGER.debug("Fetching shops from Etsy API")
            
            shops_response = await session.get(shops_url, headers=headers)
            
            if shops_response.status != 200:
                error_text = await shops_response.text()
                _LOGGER.error(f"Failed to fetch shops. Status: {shops_response.status}, Error: {error_text}")
                return []
                
            shops_data = await shops_response.json()
            _LOGGER.debug("Processing shops response from Etsy API")
            
            # The API can return data in different formats:
            # 1. Single shop: {"shop_id": 123, "shop_name": "...", ...}
            # 2. Multiple shops: {"count": 2, "results": [{shop1}, {shop2}]}
            # 3. Empty/No shops: {"count": 0, "results": []}
            
            if isinstance(shops_data, dict):
                if "results" in shops_data:
                    # Standard v3 format with results array
                    shops = shops_data["results"]
                    _LOGGER.debug("Found %s shop(s) in results array", shops_data.get('count', len(shops)))
                    return shops
                elif "shop_id" in shops_data:
                    # Single shop returned directly (seen in your logs)
                    _LOGGER.debug("Single shop returned directly from API")
                    return [shops_data]
                else:
                    _LOGGER.warning(f"Unexpected shops API response format: {shops_data.keys()}")
            elif isinstance(shops_data, list):
                # In case API returns a direct array of shops
                _LOGGER.debug("API returned direct array of %s shop(s)", len(shops_data))
                return shops_data
            
            return []
            
        except Exception as e:
            _LOGGER.error("Error fetching user shops: %s", e)
            return []

    async def _validate_shop_access(self, shop_id: str) -> bool:
        """Validate that we can access the specified shop."""
        try:
            session = async_get_clientsession(self.hass)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": self.flow_impl.client_id,
                "Authorization": f"Bearer {self.access_token}",
            }
            
            response = await session.get(
                f"{ETSY_API_BASE}/shops/{shop_id}", headers=headers
            )
            
            if response.status == 200:
                shop_data = await response.json()
                if shop_data.get("results"):
                    self._shop_name = shop_data["results"][0]["shop_name"]
                    return True
            return False
            
        except Exception as e:
            _LOGGER.error("Error validating shop access: %s", e)
            return False

    async def _create_config_entry(self) -> FlowResult:
        """Create the config entry."""
        # Use shop name with ID and connection type for clarity
        title = f"{self._shop_name} ({self._shop_id}) - Direct" if self._shop_name else f"Etsy Shop {self._shop_id} - Direct"

        # Include client_id for direct mode
        config_data = {
            **self.oauth_data,
            "shop_id": self._shop_id,
            "shop_name": self._shop_name,
            CONF_CONNECTION_MODE: CONNECTION_MODE_DIRECT,
        }

        # Add client_id and client_secret for direct mode (needed for OAuth and API headers)
        if self.etsy_credentials:
            config_data["auth_implementation_client_id"] = self.etsy_credentials.get(CONF_CLIENT_ID)
            config_data["client_secret"] = self.etsy_credentials.get(CONF_CLIENT_SECRET)

        return self.async_create_entry(
            title=title,
            data=config_data,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return EtsyOptionsFlow()


class EtsyOptionsFlow(config_entries.OptionsFlow):
    """Handle Etsy Shop options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Access config_entry via the property (automatically set by HA)
        current_options = self.config_entry.options if hasattr(self, 'config_entry') else {}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "listings_display_limit",
                    default=current_options.get("listings_display_limit", 5),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=25)),
                vol.Optional(
                    "transactions_display_limit", 
                    default=current_options.get("transactions_display_limit", 10),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=25)),
                vol.Optional(
                    "stock_threshold",
                    default=current_options.get("stock_threshold", 5),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            }),
        )