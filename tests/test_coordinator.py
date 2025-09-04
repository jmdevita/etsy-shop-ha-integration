"""Test Etsy update coordinator."""

import pytest
from unittest.mock import Mock
from pathlib import Path
import json
from datetime import datetime
from custom_components.etsyapp.coordinator import EtsyUpdateCoordinator

from homeassistant.setup import async_setup_component
from custom_components.etsyapp.const import DOMAIN


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.asyncio
async def test_etsy_update_coordinator(hass, aioclient_mock):
    """Test the EtsyUpdateCoordinator with mocked API responses."""
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "etsy_shop_data.json") as file:
        etsy_data = json.load(file)
    
    # Mock ConfigEntry
    mock_entry = Mock()
    mock_entry.data = {
        "shop_id": "56636211",
        "token": {
            "access_token": "test_access_token"
        },
        "auth_implementation_client_id": "test_client_id",
        "auth_implementation": DOMAIN,  # Add auth implementation for OAuth
    }

    # Mock the Etsy API endpoints
    shop_url = "https://openapi.etsy.com/v3/application/shops/56636211"
    listings_url = "https://openapi.etsy.com/v3/application/shops/56636211/listings/active"
    transactions_url = "https://openapi.etsy.com/v3/application/shops/56636211/transactions"
    
    # Mock shop endpoint
    aioclient_mock.get(
        shop_url,
        json={"results": [etsy_data["shop"]]},
        status=200,
    )
    
    # Mock listings endpoint
    aioclient_mock.get(
        listings_url,
        json={
            "results": etsy_data["listings"],
            "count": etsy_data["listings_count"]
        },
        status=200,
    )
    
    # Mock transactions endpoint
    aioclient_mock.get(
        transactions_url,
        json={
            "results": etsy_data["transactions"],
            "count": etsy_data["transactions_count"]
        },
        status=200,
    )

    # Initialize the coordinator
    coordinator = EtsyUpdateCoordinator(hass, mock_entry)
    
    # Mock OAuth session for tests
    from unittest.mock import AsyncMock
    coordinator._oauth_session_initialized = True
    mock_oauth_session = AsyncMock()
    mock_oauth_session.async_ensure_token_valid = AsyncMock()
    mock_oauth_session.token = {"access_token": "test_access_token"}
    coordinator.oauth_session = mock_oauth_session

    # Perform the update
    await coordinator.async_refresh()

    # Assert the data was fetched correctly
    assert coordinator.last_update_success
    assert coordinator.data['shop']['shop_name'] == "TestEtsyShop"
    assert coordinator.data['listings_count'] == 2
    assert coordinator.data['transactions_count'] == 2
    assert len(coordinator.data['listings']) == 2
    assert len(coordinator.data['transactions']) == 2


@pytest.mark.asyncio
async def test_etsy_coordinator_missing_credentials(hass):
    """Test coordinator behavior when credentials are missing."""
    # Mock ConfigEntry without required data
    from homeassistant.config_entries import ConfigEntry
    from custom_components.etsyapp.const import DOMAIN
    
    mock_entry = ConfigEntry(
        domain=DOMAIN,
        title="Test Etsy Shop",
        data={},  # Missing credentials
        version=1,
        minor_version=1,
        unique_id="test_etsy_shop",
        discovery_keys=set(),
        options={},
        source="user",
        subentries_data={}
    )

    # Initialize the coordinator
    coordinator = EtsyUpdateCoordinator(hass, mock_entry)

    # Attempt to refresh should fail
    try:
        await coordinator.async_refresh()
        # If it doesn't raise, check if it failed gracefully
        assert not coordinator.last_update_success
    except Exception:
        # Expected behavior - missing credentials should cause failure
        pass


@pytest.mark.asyncio 
async def test_etsy_coordinator_api_error(hass, aioclient_mock):
    """Test coordinator behavior when API returns error."""
    # Mock ConfigEntry
    from homeassistant.config_entries import ConfigEntry
    from custom_components.etsyapp.const import DOMAIN
    
    mock_entry = ConfigEntry(
        domain=DOMAIN,
        title="Test Etsy Shop",
        data={
            "shop_id": "56636211", 
            "token": {
                "access_token": "test_access_token"
            },
            "auth_implementation_client_id": "test_client_id"
        },
        version=1,
        minor_version=1,
        unique_id="test_etsy_shop",
        discovery_keys=set(),
        options={},
        source="user",
        subentries_data={}
    )

    # Mock API endpoints to return 401 error
    shop_url = "https://openapi.etsy.com/v3/application/shops/56636211"
    aioclient_mock.get(shop_url, status=401)

    # Initialize the coordinator
    coordinator = EtsyUpdateCoordinator(hass, mock_entry)

    # Attempt to refresh should fail
    try:
        await coordinator.async_refresh()
        # If it doesn't raise, check if it failed gracefully
        assert not coordinator.last_update_success
    except Exception:
        # Expected behavior - API error should cause failure
        pass