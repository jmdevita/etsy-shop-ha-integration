"""Tests for entry-scoped device registry lookups."""

from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.etsyapp import cleanup_old_device
from custom_components.etsyapp.const import DOMAIN
from custom_components.etsyapp.utils import async_get_entry_device


async def test_get_entry_device_scoped_to_entry(hass):
    """Only the device attached to the given entry is returned."""
    entry_a = MockConfigEntry(domain=DOMAIN, entry_id="entry_a")
    entry_b = MockConfigEntry(domain=DOMAIN, entry_id="entry_b")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    registry = dr.async_get(hass)
    device_a = registry.async_get_or_create(
        config_entry_id="entry_a", identifiers={(DOMAIN, "entry_a")}
    )
    registry.async_get_or_create(
        config_entry_id="entry_b", identifiers={(DOMAIN, "entry_b")}
    )

    assert async_get_entry_device(hass, "entry_a").id == device_a.id
    assert async_get_entry_device(hass, "missing") is None


async def test_cleanup_old_device_removes_malformed_identifier(hass):
    """A legacy device with a bare (DOMAIN,) identifier is removed."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="entry_a")
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    old = registry.async_get_or_create(
        config_entry_id="entry_a", identifiers={(DOMAIN,)}
    )
    good = registry.async_get_or_create(
        config_entry_id="entry_a", identifiers={(DOMAIN, "entry_a")}
    )

    await cleanup_old_device(hass, "entry_a")

    assert registry.async_get(old.id) is None
    assert registry.async_get(good.id) is not None
