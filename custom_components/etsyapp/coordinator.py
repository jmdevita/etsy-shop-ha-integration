"""Integration for Etsy shop monitoring coordinator."""

from collections import defaultdict
from datetime import timedelta, datetime
import asyncio
import json
import logging
import random
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, 
    ETSY_API_BASE, 
    UPDATE_INTERVAL_SECONDS,
    API_FETCH_LIMIT,
    CONNECTION_MODE_DIRECT,
    CONNECTION_MODE_PROXY,
    CONF_CONNECTION_MODE,
    CONF_PROXY_URL,
    CONF_PROXY_API_KEY,
    CONF_HMAC_SECRET,
)
from .hmac_client import HMACClient
from .utils import build_receipt_summary, build_transaction_detail

_LOGGER = logging.getLogger(__name__)
type EtsyConfigEntry = ConfigEntry[EtsyUpdateCoordinator]


class EtsyUpdateCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data update coordinator."""
        self._hass = hass
        self.config_entry = entry
        self.session = async_get_clientsession(self._hass)
        self.shop_data = {"last_updated": "", "shop_info": {}}
        # Track previous state for change detection
        self._prev_transactions_count = 0
        self._prev_review_count = 0
        self._prev_receipt_ids: set[str] = set()
        # Rate limiting with exponential backoff
        self._retry_count = 0
        self._max_retries = 5
        self._base_delay = 1  # Start with 1 second
        # Cache last successful data to prevent unavailability during token refresh
        self._last_successful_data = None
        self._consecutive_failures = 0
        
        # Determine connection mode
        self.connection_mode = entry.data.get(CONF_CONNECTION_MODE, CONNECTION_MODE_DIRECT)
        
        if self.connection_mode == CONNECTION_MODE_PROXY:
            # Proxy mode configuration
            self.proxy_url = entry.data.get(CONF_PROXY_URL)
            self.proxy_api_key = entry.data.get(CONF_PROXY_API_KEY)
            hmac_secret = entry.data.get(CONF_HMAC_SECRET)
            # Initialize HMAC client for secure communication
            self.hmac_client = HMACClient(self.proxy_api_key, hmac_secret) if hmac_secret else None
            # For proxy mode, we'll get shop_id from the proxy service
            self.shop_id = entry.data.get("shop_id")
            self.oauth_session = None
            self._oauth_session_initialized = True  # No OAuth for proxy mode
        else:
            # Direct mode configuration
            self.shop_id = entry.data.get("shop_id")
            # OAuth2Session will be initialized lazily on first use
            self.oauth_session = None
            self._oauth_session_initialized = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=False,  # Changed to False per HA best practices for performance
        )
        
        _LOGGER.info(
            "Initialized Etsy coordinator for shop %s with %s mode, update interval: %s seconds",
            self.shop_id,
            self.connection_mode,
            UPDATE_INTERVAL_SECONDS
        )
    
    async def _get_oauth_implementation(self):
        """Get OAuth implementation for this integration."""
        try:
            from homeassistant.helpers import config_entry_oauth2_flow
            return await config_entry_oauth2_flow.async_get_config_entry_implementation(
                self._hass, self.config_entry
            )
        except Exception as err:
            _LOGGER.debug("OAuth implementation not available: %s", err)
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Etsy API and return shop information."""
        try:
            if self.connection_mode == CONNECTION_MODE_PROXY:
                data = await self._fetch_with_retry(self._fetch_via_proxy)
            else:
                data = await self._fetch_with_retry(self._fetch_direct)
            
            # Check for changes and fire events
            if data:
                await self._check_for_changes(data)
                # Reset retry count on successful fetch
                self._retry_count = 0
                # Store successful data for use during temporary failures
                self._last_successful_data = data
                self._consecutive_failures = 0
                _LOGGER.debug("Successfully fetched data for shop %s", self.shop_id)
            
            return data
        except ConfigEntryAuthFailed:
            # Authentication failures need to trigger reauth flow
            _LOGGER.error("Authentication failed, triggering reauth flow")
            raise
        except Exception as err:
            self._consecutive_failures += 1
            error_str = str(err).lower()
            
            # Check if this is a temporary failure that shouldn't cause unavailability
            is_temporary = (
                "rate limit" in error_str or 
                "429" in error_str or
                "token" in error_str or
                "refresh" in error_str or
                "timeout" in error_str or
                "connection" in error_str
            )
            
            if is_temporary and self._last_successful_data:
                # Return cached data for temporary failures to prevent unavailability
                _LOGGER.warning(
                    "Temporary failure (attempt %s): %s. Using cached data to maintain availability.",
                    self._consecutive_failures,
                    err
                )
                return self._last_successful_data
            
            # For persistent failures or no cached data, raise the error
            _LOGGER.error("Failed to update data: %s", err)
            raise UpdateFailed(f"Failed to update data: {err}") from err
    
    async def _fetch_with_retry(self, fetch_func):
        """Fetch data with exponential backoff retry logic."""
        last_error = None
        
        for attempt in range(self._max_retries):
            try:
                return await fetch_func()
            except Exception as err:
                last_error = err
                error_str = str(err).lower()
                
                # Check if it's a rate limit error
                if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                    self._retry_count = attempt + 1
                    if self._retry_count < self._max_retries:
                        # Calculate exponential backoff delay
                        delay = self._base_delay * (2 ** attempt)
                        # Add jitter to prevent thundering herd
                        jitter = random.uniform(0, delay * 0.1)
                        actual_delay = delay + jitter
                        
                        _LOGGER.info(
                            "Rate limit hit, retrying in %.2f seconds (attempt %s/%s)",
                            actual_delay,
                            self._retry_count,
                            self._max_retries
                        )
                        await asyncio.sleep(actual_delay)
                        continue
                    else:
                        _LOGGER.error("Max retries reached for rate limit")
                        raise UpdateFailed(f"Rate limit exceeded after {self._max_retries} retries") from err
                
                # For non-rate-limit errors, fail immediately
                raise err
        
        # If we've exhausted all retries
        raise UpdateFailed(f"Failed after {self._max_retries} attempts: {last_error}") from last_error
    
    async def _fetch_via_proxy(self) -> dict[str, Any]:
        """Fetch data via proxy service."""
        if not self.proxy_url or not self.proxy_api_key:
            raise UpdateFailed("Missing proxy configuration")
        
        if not self.hmac_client:
            raise UpdateFailed("HMAC secret not configured for secure proxy communication")
        
        try:
            # First, get the user's shop if we don't have it
            if not self.shop_id:
                # Get shop info from proxy with HMAC signature
                path = "/api/v1/shops"
                headers = self.hmac_client.get_headers_with_signature(
                    method="GET",
                    path=path,
                    api_key=self.proxy_api_key
                )
                
                response = await self.session.get(
                    f"{self.proxy_url}{path}",
                    headers=headers,
                )
                if response.status != 200:
                    text = await response.text()
                    raise UpdateFailed(f"Failed to get shops from proxy: {text}")
                
                shops_data = await response.json()
                if shops_data and len(shops_data) > 0:
                    self.shop_id = str(shops_data[0]["shop_id"])
                else:
                    raise UpdateFailed("No shops found via proxy")
            
            # Now fetch shop data with HMAC signatures
            shop_info = await self._fetch_shop_info_proxy()
            listings_data = await self._fetch_listings_proxy()

            # Try receipts first; fall back to /transactions if the proxy
            # hasn't been upgraded yet (one-release transition window).
            receipts_data = await self._fetch_receipts_proxy()
            if receipts_data is None:
                _LOGGER.debug("Proxy /receipts unavailable, falling back to /transactions")
                transactions_data = await self._fetch_transactions_proxy()
                receipts = []
                flattened_transactions = transactions_data.get("results", []) or []
                transactions_count = transactions_data.get(
                    "count", len(flattened_transactions)
                )
                last_payment = None
            else:
                receipts = receipts_data.get("results", []) or []
                flattened_transactions = []
                for receipt in receipts:
                    flattened_transactions.extend(receipt.get("transactions") or [])
                transactions_count = len(flattened_transactions)
                last_payment = await self._fetch_last_payment_proxy(receipts)

            proxy_data = {
                "shop": shop_info,
                "listings": listings_data.get("results", []),
                "listings_count": listings_data.get("count", 0),
                "transactions": flattened_transactions,
                "receipts": receipts,
                "last_payment": last_payment,
                "transactions_count": transactions_count,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            
            # Cache successful data for use during temporary failures
            self._last_successful_data = proxy_data
            
            return proxy_data
        except Exception as e:
            _LOGGER.error("Error fetching data via proxy: %s", e)
            raise UpdateFailed(f"Failed to fetch data via proxy: {e}")
    
    async def _fetch_shop_info_proxy(self) -> dict:
        """Fetch shop info via proxy."""
        path = f"/api/v1/shops/{self.shop_id}"
        headers = self.hmac_client.get_headers_with_signature(
            method="GET",
            path=path,
            api_key=self.proxy_api_key
        )
        
        response = await self.session.get(
            f"{self.proxy_url}{path}",
            headers=headers,
        )
        if response.status == 429:
            text = await response.text()
            raise UpdateFailed(f"Rate limit exceeded (429): {text}")
        if response.status != 200:
            text = await response.text()
            raise UpdateFailed(f"Failed to get shop info: {text}")
        return await response.json()
    
    async def _fetch_listings_proxy(self) -> dict:
        """Fetch listings via proxy."""
        # Limit listings for performance
        params = {"limit": API_FETCH_LIMIT}
        path = f"/api/v1/shops/{self.shop_id}/listings/active"
        headers = self.hmac_client.get_headers_with_signature(
            method="GET",
            path=path,
            api_key=self.proxy_api_key
        )
        
        response = await self.session.get(
            f"{self.proxy_url}{path}",
            headers=headers,
            params=params,
        )
        if response.status != 200:
            text = await response.text()
            _LOGGER.warning("Failed to get listings: %s", text)
            return {"results": [], "count": 0}
        return await response.json()
    
    async def _fetch_transactions_proxy(self) -> dict:
        """Fetch transactions via proxy (legacy fallback for older proxies)."""
        path = f"/api/v1/shops/{self.shop_id}/transactions"
        headers = self.hmac_client.get_headers_with_signature(
            method="GET",
            path=path,
            api_key=self.proxy_api_key
        )

        response = await self.session.get(
            f"{self.proxy_url}{path}",
            headers=headers,
        )
        if response.status != 200:
            text = await response.text()
            _LOGGER.warning("Failed to get transactions: %s", text)
            return {"results": []}
        return await response.json()

    async def _fetch_receipts_proxy(self) -> dict | None:
        """Fetch receipts via proxy. Returns None if the proxy doesn't support
        the endpoint yet (404), signalling a fallback to /transactions."""
        path = f"/api/v1/shops/{self.shop_id}/receipts"
        headers = self.hmac_client.get_headers_with_signature(
            method="GET",
            path=path,
            api_key=self.proxy_api_key,
        )
        params = {
            "limit": API_FETCH_LIMIT,
            "was_paid": "true",
        }
        response = await self.session.get(
            f"{self.proxy_url}{path}",
            headers=headers,
            params=params,
        )
        if response.status == 404:
            return None
        if response.status != 200:
            text = await response.text()
            _LOGGER.warning("Failed to get receipts: %s", text)
            return {"results": []}
        data = await response.json()
        # Sort client-side — Etsy's /receipts default order isn't documented.
        results = data.get("results") or []
        results.sort(
            key=lambda r: r.get("created_timestamp") or 0,
            reverse=True,
        )
        data["results"] = results
        return data

    async def _fetch_last_payment_proxy(self, receipts: list[dict]) -> dict | None:
        """Fetch the payment for the most recent receipt via proxy. Best-effort."""
        if not receipts:
            return None
        receipt_id = receipts[0].get("receipt_id")
        if not receipt_id:
            return None
        path = f"/api/v1/shops/{self.shop_id}/receipts/{receipt_id}/payments"
        headers = self.hmac_client.get_headers_with_signature(
            method="GET",
            path=path,
            api_key=self.proxy_api_key,
        )
        try:
            response = await self.session.get(
                f"{self.proxy_url}{path}",
                headers=headers,
            )
            if response.status != 200:
                _LOGGER.debug(
                    "Proxy payment fetch skipped for receipt %s (status %s)",
                    receipt_id,
                    response.status,
                )
                return None
            data = await response.json()
            results = data.get("results") if isinstance(data, dict) else data
            if isinstance(results, list) and results:
                return results[0]
            if isinstance(data, dict) and data.get("amount_net"):
                return data
            return None
        except Exception as err:
            _LOGGER.debug("Proxy payment fetch failed for receipt %s: %s", receipt_id, err)
            return None
    
    async def _fetch_direct(self) -> dict[str, Any]:
        """Fetch data directly from Etsy API with automatic token refresh."""
        if not self.shop_id:
            raise UpdateFailed("Missing shop_id")
        
        # Always try to initialize OAuth session for token refresh capability
        if not self._oauth_session_initialized:
            try:
                implementation = await self._get_oauth_implementation()
                if implementation:
                    # Create OAuth session with the stored token
                    self.oauth_session = OAuth2Session(self._hass, self.config_entry, implementation)
                    _LOGGER.debug("OAuth session initialized with implementation")
                else:
                    # Implementation not available, create a basic session
                    self.oauth_session = None
                    _LOGGER.debug("OAuth implementation not available, will attempt manual token refresh")
                self._oauth_session_initialized = True
            except Exception as err:
                _LOGGER.warning("Failed to initialize OAuth session: %s", err)
                self.oauth_session = None
                self._oauth_session_initialized = True
            
        # Get client_id from entry for API key header
        client_id = self.config_entry.data.get("auth_implementation_client_id")
        if not client_id:
            raise UpdateFailed("Missing client_id for API authentication")
        
        # Get access token with refresh handling
        token = None
        token_refreshed = False
        
        if self.oauth_session:
            # Use OAuth session for automatic token refresh
            try:
                await self.oauth_session.async_ensure_token_valid()
                token = self.oauth_session.token["access_token"]
                _LOGGER.debug("Token is valid, proceeding with API calls")
            except Exception as err:
                _LOGGER.info("OAuth session token needs refresh: %s", err)
                # Try manual refresh as fallback
                token = await self._manual_token_refresh()
                if not token:
                    # Only raise auth error if we don't have cached data
                    if self._last_successful_data:
                        _LOGGER.warning("Token refresh failed, returning cached data to maintain availability")
                        return self._last_successful_data
                    raise ConfigEntryAuthFailed("Token refresh failed. Please re-authenticate.") from err
                token_refreshed = True
                _LOGGER.info("Token refreshed successfully via manual refresh")
        else:
            # No OAuth session, try manual refresh if token expired
            token_data = self.config_entry.data.get("token", {})
            token = token_data.get("access_token")
            expires_at = token_data.get("expires_at", 0)
            
            # Check if token is expired (with 60 second buffer)
            if expires_at and time.time() > (expires_at - 60):
                _LOGGER.info(
                    "Token expiring soon (expires: %s, current: %s), refreshing...",
                    datetime.fromtimestamp(expires_at).strftime("%H:%M:%S"),
                    datetime.now().strftime("%H:%M:%S")
                )
                refreshed_token = await self._manual_token_refresh()
                if refreshed_token:
                    token = refreshed_token
                    token_refreshed = True
                    _LOGGER.info("Token refreshed successfully")
                else:
                    # Use cached data if available instead of going unavailable
                    if self._last_successful_data:
                        _LOGGER.warning("Token refresh failed, using cached data to maintain availability")
                        return self._last_successful_data
                    # Only trigger reauth if we have no cached data
                    self.config_entry.async_start_reauth(self._hass)
                    raise ConfigEntryAuthFailed("Token expired and refresh failed. Please re-authenticate.")
            
            if not token:
                raise UpdateFailed("No access token available")
            
            _LOGGER.debug("Using token from config entry")
            
        try:
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json", 
                "x-api-key": client_id,
                "Authorization": f"Bearer {token}",
            }
            
            # Get shop information
            shop_url = f"{ETSY_API_BASE}/shops/{self.shop_id}"
            shop_response = await self.session.get(shop_url, headers=headers)
            
            # Check for authentication errors
            if shop_response.status == 401:
                _LOGGER.error("Authentication failed - token may be expired")
                raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.")
            
            # Check for rate limiting
            if shop_response.status == 429:
                retry_after = shop_response.headers.get("Retry-After", "60")
                _LOGGER.warning("Etsy API rate limit hit. Retry after %s seconds", retry_after)
                raise UpdateFailed(f"Rate limit exceeded (429). Retry after {retry_after} seconds")
            
            shop_response.raise_for_status()
            shop_data_raw = await shop_response.json()
            
            # Shop endpoint returns either direct object or wrapped in results
            if isinstance(shop_data_raw, dict):
                if "results" in shop_data_raw and isinstance(shop_data_raw["results"], list):
                    shop_data = shop_data_raw["results"][0] if shop_data_raw["results"] else {}
                else:
                    # Direct shop object
                    shop_data = shop_data_raw
            else:
                shop_data = {}
            
            # Get active listings (limited for performance)
            listings_url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings/active"
            listings_params = {"limit": API_FETCH_LIMIT}
            listings_response = await self.session.get(
                listings_url, headers=headers, params=listings_params
            )
            
            # Check for rate limiting
            if listings_response.status == 429:
                retry_after = listings_response.headers.get("Retry-After", "60")
                _LOGGER.warning("Etsy API rate limit hit on listings. Retry after %s seconds", retry_after)
                raise UpdateFailed(f"Rate limit exceeded (429). Retry after {retry_after} seconds")
            
            listings_response.raise_for_status()
            listings_data = await listings_response.json()
            
            # Get recent receipts (replaces /transactions — receipts embed their
            # transactions array and additionally carry buyer name + order totals).
            # Etsy's /receipts endpoint doesn't accept sort_on/sort_order params
            # and doesn't document its default order, so we sort client-side
            # to guarantee receipts[0] is the most recent.
            receipts_url = f"{ETSY_API_BASE}/shops/{self.shop_id}/receipts"
            receipts_params = {
                "limit": API_FETCH_LIMIT,
                "was_paid": "true",
            }
            receipts_response = await self.session.get(
                receipts_url, headers=headers, params=receipts_params
            )

            if receipts_response.status == 429:
                retry_after = receipts_response.headers.get("Retry-After", "60")
                _LOGGER.warning("Etsy API rate limit hit on receipts. Retry after %s seconds", retry_after)
                raise UpdateFailed(f"Rate limit exceeded (429). Retry after {retry_after} seconds")

            receipts_response.raise_for_status()
            receipts_data = await receipts_response.json()
            receipts = receipts_data.get("results", []) or []
            receipts.sort(
                key=lambda r: r.get("created_timestamp") or 0,
                reverse=True,
            )

            # Flatten transactions out of receipts to preserve data["transactions"]
            # for EtsyRecentOrders, EtsyShopStats and services.py.
            flattened_transactions = []
            for receipt in receipts:
                flattened_transactions.extend(receipt.get("transactions") or [])

            # Best-effort fetch of payment for the most recent receipt only —
            # /payments is one call per receipt, and only EtsyLastOrder
            # surfaces amount_net.
            last_payment = await self._fetch_last_payment_direct(receipts, headers)

            # Combine data
            combined_data = {
                "shop": shop_data,  # Already extracted above
                "listings": listings_data.get("results", []),
                "transactions": flattened_transactions,
                "receipts": receipts,
                "last_payment": last_payment,
                "listings_count": listings_data.get("count", 0),
                "transactions_count": len(flattened_transactions),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            
            # Cache successful data for use during token refresh
            self._last_successful_data = combined_data
            
            return combined_data
            
        except ConfigEntryAuthFailed:
            # Re-raise authentication failures without wrapping
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching data from Etsy API: {err}") from err

    async def _fetch_last_payment_direct(
        self, receipts: list[dict], headers: dict
    ) -> dict | None:
        """Fetch the payment for the most recent receipt. Best-effort.

        amount_net (the seller's net payout after Etsy fees) lives on the
        payment object, not the receipt. We only fetch it for the latest
        receipt to keep API usage in check — EtsyLastOrder is the only sensor
        that surfaces net payout.
        """
        if not receipts:
            return None
        receipt_id = receipts[0].get("receipt_id")
        if not receipt_id:
            return None
        try:
            url = f"{ETSY_API_BASE}/shops/{self.shop_id}/receipts/{receipt_id}/payments"
            response = await self.session.get(url, headers=headers)
            if response.status != 200:
                _LOGGER.debug(
                    "Skipping payment fetch for receipt %s (status %s)",
                    receipt_id,
                    response.status,
                )
                return None
            data = await response.json()
            # Endpoint returns a list (a receipt can have multiple payments,
            # one per payment method); take the first.
            results = data.get("results") if isinstance(data, dict) else data
            if isinstance(results, list) and results:
                return results[0]
            if isinstance(data, dict) and data.get("amount_net"):
                return data
            return None
        except Exception as err:
            _LOGGER.debug("Payment fetch failed for receipt %s: %s", receipt_id, err)
            return None

    async def _manual_token_refresh(self) -> str | None:
        """Manually refresh the OAuth token using the refresh token."""
        try:
            token_data = self.config_entry.data.get("token", {})
            refresh_token = token_data.get("refresh_token")
            
            if not refresh_token:
                _LOGGER.error("No refresh token available for manual refresh")
                return None
            
            client_id = self.config_entry.data.get("auth_implementation_client_id")
            client_secret = self.config_entry.data.get("client_secret")
            
            if not client_id or not client_secret:
                _LOGGER.error("Missing client credentials for token refresh")
                # Trigger re-authentication flow when credentials are missing
                self.config_entry.async_start_reauth(self._hass)
                return None
            
            # Prepare token refresh request
            refresh_url = "https://api.etsy.com/v3/public/oauth/token"
            refresh_data = {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            }
            
            async with self.session.post(refresh_url, data=refresh_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error("Token refresh failed: %s", error_text)
                    return None
                
                new_token_data = await response.json()
                
                # Update the config entry with new token
                new_data = dict(self.config_entry.data)
                new_data["token"] = {
                    "access_token": new_token_data["access_token"],
                    "refresh_token": new_token_data.get("refresh_token", refresh_token),
                    "expires_in": new_token_data.get("expires_in", 3600),
                    "expires_at": time.time() + new_token_data.get("expires_in", 3600),
                    "token_type": "Bearer",
                }
                
                # Update the config entry
                self._hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data
                )
                
                _LOGGER.info(
                    "Successfully refreshed OAuth token (expires: %s)",
                    datetime.fromtimestamp(time.time() + new_token_data.get("expires_in", 3600)).strftime("%H:%M:%S")
                )
                return new_token_data["access_token"]
                
        except Exception as err:
            _LOGGER.error("Manual token refresh failed: %s", err)
            return None
    
    async def _check_for_changes(self, data: dict[str, Any]) -> None:
        """Check for changes in data and fire device trigger events."""
        # Get device ID for this integration
        from homeassistant.helpers import device_registry as dr
        
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.config_entry.entry_id)}
        )
        
        if not device:
            return
        
        device_id = device.id
        shop = data.get("shop", {})
        
        # Check for new orders. `new_orders` count is preserved as a delta of
        # transaction line items (legacy behavior — automations may template
        # off it). The richer `receipts` payload is built from real receipt
        # data when available, diffed by receipt_id.
        current_transactions_count = data.get("transactions_count", 0)
        current_receipts = data.get("receipts") or []
        current_receipt_ids = {
            str(r.get("receipt_id")) for r in current_receipts if r.get("receipt_id")
        }

        if current_transactions_count > self._prev_transactions_count and self._prev_transactions_count > 0:
            new_order_count = current_transactions_count - self._prev_transactions_count
            _LOGGER.debug(
                "New order detected! Transaction count %s -> %s",
                self._prev_transactions_count,
                current_transactions_count,
            )

            transactions = data.get("transactions", [])
            new_transactions = [
                build_transaction_detail(t) for t in transactions[:new_order_count]
            ]

            # Build receipts payload — prefer real receipts diffed by ID,
            # fall back to client-side grouping when receipt data isn't
            # present (legacy proxy path).
            new_receipt_ids = current_receipt_ids - self._prev_receipt_ids
            if current_receipts and new_receipt_ids:
                new_receipts = [
                    build_receipt_summary(r)
                    for r in current_receipts
                    if str(r.get("receipt_id")) in new_receipt_ids
                ]
            else:
                receipt_groups: dict[str, list[dict]] = defaultdict(list)
                for detail in new_transactions:
                    key = detail.get("receipt_id") or detail.get("transaction_id") or ""
                    receipt_groups[key].append(detail)
                new_receipts = [
                    {
                        "receipt_id": rid,
                        "buyer_user_id": items[0].get("buyer_user_id"),
                        "item_count": len(items),
                        "items": items,
                    }
                    for rid, items in receipt_groups.items()
                ]

            self._hass.bus.async_fire(
                f"{DOMAIN}_new_order",
                {
                    "device_id": device_id,
                    "shop_name": shop.get("shop_name"),
                    "new_orders": new_order_count,
                    "orders": new_transactions,
                    "receipts": new_receipts,
                }
            )
        self._prev_transactions_count = current_transactions_count
        self._prev_receipt_ids = current_receipt_ids
        
        # Check for new reviews
        current_review_count = shop.get("review_count", 0)
        if current_review_count > self._prev_review_count and self._prev_review_count > 0:
            _LOGGER.debug("New review detected! Count increased from %s to %s", self._prev_review_count, current_review_count)
            self._hass.bus.async_fire(
                f"{DOMAIN}_new_review",
                {
                    "device_id": device_id,
                    "shop_name": shop.get("shop_name"),
                    "new_reviews": current_review_count - self._prev_review_count,
                    "average_rating": shop.get("review_average", 0),
                }
            )
        self._prev_review_count = current_review_count
        
        # Check for low stock
        listings = data.get("listings", [])
        for listing in listings:
            quantity = listing.get("quantity", 0)
            # Get the stock threshold from options, default to 5
            stock_threshold = self.config_entry.options.get("stock_threshold", 5)
            if quantity > 0 and quantity <= stock_threshold:
                _LOGGER.debug("Low stock detected for listing: %s (quantity: %s)", listing.get('title'), quantity)
                self._hass.bus.async_fire(
                    f"{DOMAIN}_low_stock",
                    {
                        "device_id": device_id,
                        "shop_name": shop.get("shop_name"),
                        "listing_id": listing.get("listing_id"),
                        "listing_title": listing.get("title"),
                        "quantity": quantity,
                        "threshold": stock_threshold,
                    }
                )
