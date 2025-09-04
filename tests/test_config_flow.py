"""Test config flow for Etsy Shop integration."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.etsyapp.const import DOMAIN
from custom_components.etsyapp.config_flow import EtsyFlowHandler


@pytest.mark.asyncio
async def test_oauth_flow_success(hass):
    """Test successful OAuth flow."""
    
    # Mock the OAuth implementation
    mock_impl = Mock()
    mock_impl.client_id = "test_client_id"
    
    # Create flow handler
    flow = EtsyFlowHandler()
    flow.hass = hass
    flow.flow_impl = mock_impl
    
    # Mock OAuth data
    flow.oauth_data = {
        "token": {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token"
        },
        "auth_implementation_client_id": "test_client_id"
    }
    
    # Mock shop data response
    mock_shops = [
        {"shop_id": 123, "shop_name": "Test Shop"}
    ]
    
    with patch.object(flow, '_get_user_shops', return_value=mock_shops), \
         patch.object(flow, '_validate_shop_access', return_value=True):
        
        result = await flow.async_oauth_create_entry(flow.oauth_data)
        
        # Should proceed to shop selection, which auto-selects single shop
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Shop (123) - Direct"
        assert result["data"]["shop_id"] == "123"


@pytest.mark.asyncio
async def test_oauth_flow_multiple_shops(hass):
    """Test OAuth flow with multiple shops."""
    
    # Mock the OAuth implementation
    mock_impl = Mock()
    mock_impl.client_id = "test_client_id"
    
    # Create flow handler
    flow = EtsyFlowHandler()
    flow.hass = hass
    flow.flow_impl = mock_impl
    
    # Mock OAuth data
    flow.oauth_data = {
        "token": {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token"
        },
        "auth_implementation_client_id": "test_client_id"
    }
    
    # Mock multiple shops response
    mock_shops = [
        {"shop_id": 123, "shop_name": "Test Shop 1"},
        {"shop_id": 456, "shop_name": "Test Shop 2"}
    ]
    
    with patch.object(flow, '_get_user_shops', return_value=mock_shops):
        
        result = await flow.async_oauth_create_entry(flow.oauth_data)
        
        # Should show shop selection form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "shop_selection"


@pytest.mark.asyncio
async def test_oauth_flow_no_shops(hass):
    """Test OAuth flow when no shops found."""
    
    # Mock the OAuth implementation
    mock_impl = Mock()
    mock_impl.client_id = "test_client_id"
    
    # Create flow handler
    flow = EtsyFlowHandler()
    flow.hass = hass
    flow.flow_impl = mock_impl
    
    # Mock OAuth data
    flow.oauth_data = {
        "token": {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token"
        },
        "auth_implementation_client_id": "test_client_id"
    }
    
    with patch.object(flow, '_get_user_shops', return_value=[]):
        
        result = await flow.async_oauth_create_entry(flow.oauth_data)
        
        # Should abort with no shops found
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_shops_found"


def test_extra_authorize_data():
    """Test extra authorize data for OAuth implementation."""
    from custom_components.etsyapp.config_flow import EtsyOAuth2Implementation
    from unittest.mock import Mock
    
    # Create a mock hass object
    hass = Mock()
    
    # Test the implementation class which has the extra_authorize_data
    impl = EtsyOAuth2Implementation(
        hass=hass,
        domain="etsyapp",
        client_id="test_client_id",
        client_secret="test_client_secret"
    )
    
    extra_data = impl.extra_authorize_data
    
    assert extra_data["response_type"] == "code"
    assert extra_data["code_challenge_method"] == "S256"
    assert "code_challenge" in extra_data  # PKCE challenge should be present
    assert "transactions_r" in extra_data["scope"]
    assert "listings_r" in extra_data["scope"]
    assert "shops_r" in extra_data["scope"]