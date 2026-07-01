"""Test Etsy device triggers."""

import pytest

from custom_components.etsyapp import device_trigger
from custom_components.etsyapp.const import DOMAIN


def _config(device_id: str, trigger_type: str = "new_order") -> dict:
    return {
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device_id,
        "type": trigger_type,
    }


@pytest.mark.asyncio
async def test_attach_trigger_fires_on_matching_event(hass):
    """async_attach_trigger must subscribe to the real etsyapp_<type> event and
    invoke the action when the event's device_id matches the configured one."""
    device_id = "test_device_id"
    calls = []

    async def action(run_variables, context=None):
        calls.append(run_variables)

    unsub = await device_trigger.async_attach_trigger(
        hass, _config(device_id), action, {"trigger_data": {}, "variables": {}}
    )

    # This is exactly what coordinator._check_for_changes / fire_test_event emit.
    hass.bus.async_fire(f"{DOMAIN}_new_order", {"device_id": device_id, "new_orders": 1})
    await hass.async_block_till_done()

    assert len(calls) == 1
    trigger = calls[0]["trigger"]
    assert trigger["platform"] == "device"
    assert trigger["event"].data["new_orders"] == 1

    unsub()


@pytest.mark.asyncio
async def test_attach_trigger_ignores_char_events_and_wrong_device(hass):
    """Regression for #28: an unvalidated event_type string was iterated
    character-by-character, so the trigger subscribed to single-letter events
    (``e``, ``t``, ``s`` ...) instead of ``etsyapp_new_order`` and never fired.
    Also assert the event_data device_id filter excludes other devices."""
    device_id = "test_device_id"
    calls = []

    async def action(run_variables, context=None):
        calls.append(run_variables)

    unsub = await device_trigger.async_attach_trigger(
        hass, _config(device_id), action, {"trigger_data": {}, "variables": {}}
    )

    # Single-letter events (what the char-iteration bug subscribed to) must be ignored.
    for char in "etsyapp_new_order":
        hass.bus.async_fire(char, {"device_id": device_id})
    # A real event for a different device must be filtered out by event_data.
    hass.bus.async_fire(f"{DOMAIN}_new_order", {"device_id": "other_device"})
    await hass.async_block_till_done()

    assert calls == []

    unsub()
