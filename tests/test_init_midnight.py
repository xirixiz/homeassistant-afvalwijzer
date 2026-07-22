"""Tests for the midnight refresh scheduling in async_setup_entry."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.afvalwijzer import async_setup_entry
from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
    DOMAIN,
)
from custom_components.afvalwijzer.coordinator import AfvalwijzerDataUpdateCoordinator
from homeassistant.util import dt as dt_util

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _setup_entry_with_mocks(hass, monkeypatch):
    """Run the real async_setup_entry with collector I/O mocked out."""
    # Re-enable the runtime setup that conftest disables globally
    monkeypatch.delenv("AFVALWIJZER_SKIP_INIT", raising=False)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "mijnafvalwijzer",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_SUFFIX: "",
        },
        options={},
    )
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        AfvalwijzerDataUpdateCoordinator,
        "async_load_cache",
        AsyncMock(return_value=True),
    )
    refresh_mock = AsyncMock()
    monkeypatch.setattr(
        AfvalwijzerDataUpdateCoordinator, "async_request_refresh", refresh_mock
    )
    monkeypatch.setattr(
        hass.config_entries, "async_forward_entry_setups", AsyncMock(return_value=True)
    )

    assert await async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()

    return entry, refresh_mock


async def _teardown_entry(hass, entry):
    """Run the entry's unload callbacks so no timers linger after the test."""
    await entry._async_process_on_unload(hass)
    await hass.async_block_till_done()


async def test_midnight_refresh_requests_coordinator_refresh(hass, monkeypatch):
    """The midnight trigger schedules a jittered coordinator refresh."""
    entry, refresh_mock = await _setup_entry_with_mocks(hass, monkeypatch)
    baseline_calls = refresh_mock.await_count

    midnight = dt_util.start_of_local_day() + timedelta(days=1)
    async_fire_time_changed(hass, midnight)
    await hass.async_block_till_done()

    # The refresh happens after a randomized jitter of at most 600 seconds
    async_fire_time_changed(hass, midnight + timedelta(seconds=601))
    await hass.async_block_till_done()

    assert refresh_mock.await_count == baseline_calls + 1

    await _teardown_entry(hass, entry)


async def test_midnight_scheduling_does_not_leak_unload_callbacks(hass, monkeypatch):
    """Repeated midnights must not grow the entry's unload callback list.

    Regression test: every midnight used to register a fresh
    async_on_unload callback, growing unboundedly over the entry's life.
    """
    entry, _ = await _setup_entry_with_mocks(hass, monkeypatch)
    baseline = len(entry._on_unload)

    midnight = dt_util.start_of_local_day() + timedelta(days=1)
    for day in range(3):
        async_fire_time_changed(hass, midnight + timedelta(days=day))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, midnight + timedelta(days=day, seconds=601))
        await hass.async_block_till_done()

    assert len(entry._on_unload) == baseline

    await _teardown_entry(hass, entry)
