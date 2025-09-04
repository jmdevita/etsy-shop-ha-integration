"""Test Etsy sensor entities."""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from pathlib import Path
from custom_components.etsyapp.sensor import (
    EtsyShopInfo, 
    EtsyActiveListings, 
    EtsyRecentOrders, 
    EtsyShopStats
)
from custom_components.etsyapp.coordinator import EtsyUpdateCoordinator


# Load the fixture data
fixtures_path = Path(__file__).parent / "fixtures"
with open(fixtures_path / "etsy_shop_data.json") as file:
    etsy_data = json.load(file)

with open(fixtures_path / "etsy_empty_data.json") as file:
    empty_data = json.load(file)


@pytest.mark.asyncio
async def test_etsy_shop_info_sensor():
    """Test the EtsyShopInfo sensor with valid data."""
    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = etsy_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyShopInfo(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == "TestEtsyShop"
    assert sensor.extra_state_attributes["shop_id"] == "56636211"  # Should be string without commas
    assert sensor.extra_state_attributes["shop_name"] == "TestEtsyShop"
    assert sensor.extra_state_attributes["currency_code"] == "USD"
    assert sensor.extra_state_attributes["title"] == "Handmade Crafts & Accessories"
    assert sensor.extra_state_attributes["transaction_sold_count"] == 1500
    assert sensor.extra_state_attributes["listing_active_count"] == 2
    assert sensor.extra_state_attributes["review_average"] == 4.8
    assert sensor.extra_state_attributes["review_count"] == 125
    assert sensor.extra_state_attributes["shop_url"] == "https://www.etsy.com/shop/TestEtsyShop"
    # Check that creation_date is formatted (not just a timestamp number)
    assert "2009-02-13" in sensor.extra_state_attributes["creation_date"]  # Date should be formatted
    assert ":" in sensor.extra_state_attributes["creation_date"]  # Should have time component


@pytest.mark.asyncio
async def test_etsy_shop_info_sensor_no_data():
    """Test the EtsyShopInfo sensor when no data is available."""
    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyShopInfo(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == "No shop data"
    assert sensor._attr_icon == "mdi:store-off"


@pytest.mark.asyncio
async def test_etsy_active_listings_sensor():
    """Test the EtsyActiveListings sensor with valid data."""
    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = etsy_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyActiveListings(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 2  # listings_count
    assert sensor.extra_state_attributes["listings_count"] == 2
    assert len(sensor.extra_state_attributes["recent_listings"]) == 2
    assert sensor.extra_state_attributes["total_views"] == 430  # 250 + 180
    assert sensor.extra_state_attributes["total_favorites"] == 20  # 12 + 8
    assert sensor._attr_icon == "mdi:numeric-2-circle"


@pytest.mark.asyncio
async def test_etsy_active_listings_sensor_empty():
    """Test the EtsyActiveListings sensor with no listings."""
    # Mock the coordinator with empty data
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = empty_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyActiveListings(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 0
    assert sensor._attr_icon == "mdi:format-list-bulleted-off"
    assert "active_listings" in sensor.extra_state_attributes or "recent_listings" in sensor.extra_state_attributes


@pytest.mark.asyncio
async def test_etsy_recent_orders_sensor():
    """Test the EtsyRecentOrders sensor with valid data."""
    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = etsy_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyRecentOrders(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 2  # transactions_count
    assert sensor.extra_state_attributes["transactions_count"] == 2
    assert len(sensor.extra_state_attributes["recent_transactions"]) == 2
    assert sensor.extra_state_attributes["total_recent_revenue"] == 70.0  # 25.00 + 45.00
    assert sensor.extra_state_attributes["currency_code"] == "USD"
    assert sensor._attr_icon == "mdi:numeric-2-circle"
    
    # Check that transaction IDs and dates are properly formatted
    first_transaction = sensor.extra_state_attributes["recent_transactions"][0]
    assert first_transaction["transaction_id"] == "111111111"  # Should be string
    assert first_transaction["listing_id"] == "123456789"  # Should be string
    assert first_transaction["buyer_user_id"] == "22222222"  # Should be string
    # Check that dates are formatted (not just timestamp numbers)
    assert "2023-09-04" in first_transaction["created_date"]  # Date should be formatted
    assert ":" in first_transaction["created_date"]  # Should have time component
    assert "2023-09-04" in first_transaction["updated_date"]  # Date should be formatted
    assert ":" in first_transaction["updated_date"]  # Should have time component


@pytest.mark.asyncio
async def test_etsy_recent_orders_sensor_empty():
    """Test the EtsyRecentOrders sensor with no transactions."""
    # Mock the coordinator with empty data
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = empty_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyRecentOrders(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 0
    assert sensor._attr_icon == "mdi:shopping-off"
    assert sensor.extra_state_attributes["recent_transactions"] == []


@pytest.mark.asyncio
async def test_etsy_shop_stats_sensor():
    """Test the EtsyShopStats sensor with valid data."""
    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = etsy_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyShopStats(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state includes "total sales" text and correct count
    assert sensor.state == "1500 total sales"
    assert sensor.extra_state_attributes["total_sales"] == 1500
    assert sensor.extra_state_attributes["active_listings"] == 2
    assert sensor.extra_state_attributes["recent_transactions"] == 2
    assert sensor.extra_state_attributes["total_views"] == 430
    assert sensor.extra_state_attributes["total_favorites"] == 20
    assert sensor.extra_state_attributes["recent_revenue"] == 70.0
    assert sensor.extra_state_attributes["shop_currency"] == "USD"
    assert sensor.extra_state_attributes["average_rating"] == 4.8
    assert sensor.extra_state_attributes["total_reviews"] == 125


@pytest.mark.asyncio
async def test_etsy_shop_stats_sensor_no_data():
    """Test the EtsyShopStats sensor when no data is available."""
    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Initialize the sensor
    sensor = EtsyShopStats(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == "No data"
    assert sensor._attr_icon == "mdi:chart-line-off"


@pytest.mark.asyncio 
async def test_all_sensors_with_partial_data():
    """Test all sensors handle partial/missing data gracefully."""
    # Create data with missing shop info
    partial_data = {
        "shop": {},
        "listings": etsy_data["listings"][:1],  # Only one listing
        "transactions": [],  # No transactions
        "listings_count": 1,
        "transactions_count": 0,
        "last_updated": etsy_data["last_updated"]
    }

    mock_coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    mock_coordinator.data = partial_data
    mock_coordinator.config_entry = AsyncMock()
    mock_coordinator.config_entry.entry_id = "test_entry_id"
    mock_coordinator.config_entry.options = {}

    # Test all sensors
    sensors = [
        EtsyShopInfo(mock_coordinator),
        EtsyActiveListings(mock_coordinator), 
        EtsyRecentOrders(mock_coordinator),
        EtsyShopStats(mock_coordinator)
    ]

    for sensor in sensors:
        await sensor.async_update()
        # All should complete without errors
        assert sensor.state is not None