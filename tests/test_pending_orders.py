"""Tests for the pending-orders (unshipped) feature — issue #24."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.etsyapp.const import PENDING_FETCH_LIMIT, PENDING_LOOKBACK_DAYS
from custom_components.etsyapp.coordinator import EtsyUpdateCoordinator
from custom_components.etsyapp.sensor import EtsyPendingOrders


fixtures_path = Path(__file__).parent / "fixtures"
with open(fixtures_path / "etsy_receipts_data.json") as file:
    receipts_fixture = json.load(file)

# Fixture 5550001 is is_shipped=false ("Paid"); 5550002 is is_shipped=true.
PENDING_RECEIPT = next(
    r for r in receipts_fixture["receipts"] if not r.get("is_shipped")
)


def _pending_coordinator_data(pending):
    """Coordinator data dict with a pending_receipts key."""
    return {
        "shop": receipts_fixture["shop"],
        "listings": [],
        "transactions": [],
        "receipts": receipts_fixture["receipts"],
        "pending_receipts": pending,
        "last_payment": None,
        "listings_count": 0,
        "transactions_count": 0,
        "last_updated": "2025-01-01 00:00:00.000000",
    }


# --- coordinator query params + filter (pure, no HTTP) ---------------------


def test_pending_query_params_are_quantized():
    """min_created is a day-quantized lookback; filter flags are set."""
    params = EtsyUpdateCoordinator._pending_query_params()

    assert params["was_paid"] == "true"
    assert params["was_shipped"] == "false"
    assert params["was_canceled"] == "false"
    assert params["limit"] == PENDING_FETCH_LIMIT

    min_created = params["min_created"]
    # Quantized to a day boundary so the proxy cache key stays stable.
    assert min_created % 86400 == 0
    expected = int(time.time() // 86400 * 86400) - PENDING_LOOKBACK_DAYS * 86400
    assert min_created == expected


def test_filter_pending_drops_shipped_canceled_refunded():
    """Keep only unshipped, still-fulfillable receipts. Shipped, canceled, and
    fully-refunded drop out; a partial refund stays (it can still ship)."""
    receipts = [
        {"receipt_id": 1, "is_shipped": False, "status": "Paid"},
        {"receipt_id": 2, "is_shipped": True, "status": "Completed"},
        {"receipt_id": 3, "is_shipped": False, "status": "Canceled"},
        {"receipt_id": 4, "is_shipped": False, "status": "Payment Processing"},
        {"receipt_id": 5, "is_shipped": False, "status": "Fully Refunded"},
        {"receipt_id": 6, "is_shipped": False, "status": "fully_refunded"},
        {"receipt_id": 7, "is_shipped": False, "status": "Partially Refunded"},
    ]
    kept = {r["receipt_id"] for r in EtsyUpdateCoordinator._filter_pending(receipts)}
    assert kept == {1, 4, 7}


# --- direct fetch: filtering + graceful degradation ------------------------


def _direct_coordinator(hass):
    mock_entry = Mock()
    mock_entry.data = {
        "shop_id": "56636211",
        "token": {"access_token": "t"},
        "auth_implementation_client_id": "test_client_id",
    }
    return EtsyUpdateCoordinator(hass, mock_entry)


@pytest.mark.asyncio
async def test_fetch_pending_direct_filters_unshipped(hass, aioclient_mock):
    """A 200 returns only the unshipped receipts, filtered client-side."""
    coordinator = _direct_coordinator(hass)
    aioclient_mock.get(
        "https://openapi.etsy.com/v3/application/shops/56636211/receipts",
        json={"results": receipts_fixture["receipts"]},
        status=200,
    )
    result = await coordinator._fetch_pending_receipts_direct({"Authorization": "Bearer t"})
    assert {str(r["receipt_id"]) for r in result} == {str(PENDING_RECEIPT["receipt_id"])}


@pytest.mark.asyncio
async def test_fetch_pending_direct_degrades_to_none(hass, aioclient_mock):
    """A non-200 returns None rather than an empty list."""
    coordinator = _direct_coordinator(hass)
    aioclient_mock.get(
        "https://openapi.etsy.com/v3/application/shops/56636211/receipts",
        status=500,
    )
    result = await coordinator._fetch_pending_receipts_direct({"Authorization": "Bearer t"})
    assert result is None


@pytest.mark.asyncio
async def test_fetch_pending_direct_raises_on_rate_limit(hass, aioclient_mock):
    """429 raises UpdateFailed (drives the coordinator's backoff)."""
    coordinator = _direct_coordinator(hass)
    aioclient_mock.get(
        "https://openapi.etsy.com/v3/application/shops/56636211/receipts",
        status=429,
        headers={"Retry-After": "30"},
    )
    with pytest.raises(UpdateFailed):
        await coordinator._fetch_pending_receipts_direct({"Authorization": "Bearer t"})


@pytest.mark.asyncio
async def test_pending_falls_back_to_last_known(hass):
    """A failed fetch (None) reuses the prior cycle's list; an empty list stays empty."""
    coordinator = _direct_coordinator(hass)
    coordinator._last_successful_data = {"pending_receipts": [{"receipt_id": 9}]}
    assert coordinator._pending_or_last_known(None) == [{"receipt_id": 9}]
    assert coordinator._pending_or_last_known([]) == []


@pytest.mark.asyncio
async def test_direct_refresh_populates_pending(hass, aioclient_mock):
    """End-to-end direct-mode refresh adds pending_receipts without disturbing
    the existing keys (non-breaking)."""
    mock_entry = Mock()
    mock_entry.data = {
        "shop_id": "56636211",
        "token": {"access_token": "test_access_token"},
        "auth_implementation_client_id": "test_client_id",
        "auth_implementation": "etsyapp",
        "client_secret": "test_secret",
    }
    base = "https://openapi.etsy.com/v3/application/shops/56636211"
    aioclient_mock.get(base, json={"results": [receipts_fixture["shop"]]}, status=200)
    aioclient_mock.get(
        f"{base}/listings/active",
        json={
            "results": receipts_fixture["listings"],
            "count": len(receipts_fixture["listings"]),
        },
        status=200,
    )
    aioclient_mock.get(
        f"{base}/receipts",
        json={
            "results": receipts_fixture["receipts"],
            "count": len(receipts_fixture["receipts"]),
        },
        status=200,
    )
    aioclient_mock.get(
        f"{base}/receipts/{PENDING_RECEIPT['receipt_id']}/payments",
        json={"results": [receipts_fixture["last_payment"]]},
        status=200,
    )

    coordinator = EtsyUpdateCoordinator(hass, mock_entry)
    coordinator._oauth_session_initialized = True
    mock_oauth = AsyncMock()
    mock_oauth.async_ensure_token_valid = AsyncMock()
    mock_oauth.token = {"access_token": "test_access_token"}
    coordinator.oauth_session = mock_oauth

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    # New additive key, filtered to the unshipped receipt only.
    assert {str(r["receipt_id"]) for r in coordinator.data["pending_receipts"]} == {
        str(PENDING_RECEIPT["receipt_id"])
    }
    # Existing keys unchanged.
    assert coordinator.data["transactions_count"] == 3
    assert len(coordinator.data["receipts"]) == 2

    # The pending fetch reached the wire with its distinct filter params.
    receipts_calls = [
        call for call in aioclient_mock.mock_calls
        if call[1].path.endswith("/shops/56636211/receipts")
    ]
    pending_calls = [
        call for call in receipts_calls
        if call[1].query.get("was_shipped") == "false"
    ]
    assert len(pending_calls) == 1
    pending_query = pending_calls[0][1].query
    assert pending_query.get("was_canceled") == "false"
    assert "min_created" in pending_query


# --- sensor ----------------------------------------------------------------


def _sensor(data):
    coordinator = AsyncMock(spec=EtsyUpdateCoordinator)
    coordinator.data = data
    coordinator.config_entry = AsyncMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.config_entry.options = {}
    sensor = EtsyPendingOrders(coordinator)
    sensor.async_write_ha_state = Mock()
    return sensor


@pytest.mark.asyncio
async def test_pending_orders_sensor():
    """State is the pending count; attributes carry per-order detail."""
    sensor = _sensor(_pending_coordinator_data([PENDING_RECEIPT]))
    sensor._handle_coordinator_update()

    assert sensor.state == 1
    attrs = sensor.extra_state_attributes
    assert attrs["pending_count"] == 1
    assert len(attrs["pending"]) == 1
    # Same per-order shape as sensor.etsy_last_order (issue #24 requirement).
    order = attrs["pending"][0]
    assert order["receipt_id"] == str(PENDING_RECEIPT["receipt_id"])
    assert order["buyer_name"] == "Jane Doe"
    assert order["is_shipped"] is False
    assert order["item_count"] == 2
    # Per-item SKU (issue #24 follow-up); null from Etsy becomes "".
    assert order["items"][0]["sku"] == "WALLET-BRN-01"
    assert order["items"][1]["sku"] == ""
    # 1 wallet + 2 keychains
    assert attrs["total_quantity"] == 3
    assert attrs["currency_code"] == "USD"
    assert sensor._attr_icon == "mdi:package-variant-closed"


@pytest.mark.asyncio
async def test_pending_orders_sensor_empty():
    """No pending orders → state 0 and an empty list."""
    sensor = _sensor(_pending_coordinator_data([]))
    sensor._handle_coordinator_update()

    assert sensor.state == 0
    assert sensor.extra_state_attributes["pending"] == []
    assert sensor._attr_icon == "mdi:package-variant"


@pytest.mark.asyncio
async def test_pending_orders_sensor_no_data():
    """No coordinator data at all → empty, no error."""
    sensor = _sensor(None)
    sensor._handle_coordinator_update()

    assert sensor.state == 0
    assert sensor.extra_state_attributes["pending"] == []
