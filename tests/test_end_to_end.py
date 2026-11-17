"""The whole integration in a real Home Assistant, with only the provider faked.

These tests set the entry up the way Home Assistant does: config entry, coordinator,
sensor and calendar platforms, entity registry and state machine.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

GETTER = "custom_components.afvalwijzer.collector.mijnafvalwijzer.get_waste_data_raw"


def _raw():
    today = dt_util.now().date()
    return [
        {"type": "gft", "date": (today + timedelta(days=2)).isoformat()},
        {"type": "papier", "date": (today + timedelta(days=9)).isoformat()},
    ]


def _entry(**options):
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "mijnafvalwijzer",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_SUFFIX: "",
        },
        options=options,
        unique_id="mijnafvalwijzer:1234AB:1",
    )


async def test_the_entry_sets_up_sensors_and_a_calendar(hass):
    """A refresh creates the waste type sensors, the custom ones and the calendar."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(GETTER, return_value=_raw()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    by_domain = {}
    for item in entities:
        by_domain.setdefault(item.domain, []).append(item.entity_id)
    assert len(by_domain["calendar"]) == 1
    sensors = by_domain["sensor"]
    assert any(entity_id.endswith("_gft") for entity_id in sensors)
    assert any(entity_id.endswith("_papier") for entity_id in sensors)
    assert any(entity_id.endswith("_next_date") for entity_id in sensors)

    gft = next(e for e in sensors if e.endswith("_gft"))
    state = hass.states.get(gft)
    assert state is not None
    assert state.state not in ("unknown", "unavailable", "geen")
    assert state.attributes["days_until_collection_date"] == 2


def _sensor(hass, entry, suffix):
    registry = er.async_get(hass)
    return next(
        item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.domain == "sensor" and item.entity_id.endswith(suffix)
    )


async def test_a_failing_first_refresh_retries_the_setup(hass):
    """When the provider is down at startup, Home Assistant retries the setup."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(
        GETTER, side_effect=ValueError("Mijnafvalwijzer request failed (HTTPError 503)")
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY

    with patch(GETTER, return_value=_raw()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED


async def test_a_refresh_that_fails_later_makes_the_sensors_unavailable_then_recovers(
    hass,
):
    """Sensors go unavailable on a failed refresh and return after the quick retry."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(GETTER, return_value=_raw()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    gft = _sensor(hass, entry, "_gft")
    assert hass.states.get(gft).state != "unavailable"

    # the regular refresh is every 4 hours; the provider is down then
    with patch(GETTER, side_effect=ValueError("down")):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=4, minutes=1))
        await hass.async_block_till_done()
    failed_state = hass.states.get(gft).state

    # a quick retry follows, and the provider is back
    with patch(GETTER, return_value=_raw()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=4, minutes=7))
        await hass.async_block_till_done()

    assert failed_state == "unavailable"
    assert hass.states.get(gft).state not in ("unavailable", "unknown")


async def test_changing_the_options_reloads_the_entry_with_the_new_settings(hass):
    """Turning off the calendar removes it, and keeps the sensors."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(GETTER, return_value=_raw()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        before = [
            item.domain
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        ]

        hass.config_entries.async_update_entry(
            entry, options={"enable_calendar": False}
        )
        await hass.async_block_till_done()

    after = [
        item.domain
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    ]
    assert "calendar" in before
    assert "calendar" not in after
    assert "sensor" in after
    assert entry.state is ConfigEntryState.LOADED


async def test_unloading_the_entry_stops_it_cleanly(hass):
    """Unload removes the coordinator and leaves no entity available."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(GETTER, return_value=_raw()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    gft = _sensor(hass, entry, "_gft")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(gft).state == "unavailable"
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_removing_the_entry_removes_its_entities_and_cache(hass):
    """Removing the entry leaves nothing of it in the registry."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(GETTER, return_value=_raw()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert er.async_entries_for_config_entry(registry, entry.entry_id) == []
