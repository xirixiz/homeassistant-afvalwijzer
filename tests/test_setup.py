"""Test basic integration setup."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.afvalwijzer import (
    CONFIG_SCHEMA,
    PLATFORMS,
    _validate_required_config,
    async_setup,
    async_setup_entry,
)
from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
    DOMAIN,
)
from custom_components.afvalwijzer.coordinator import AfvalwijzerDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryError


def test_async_setup(mock_hass):
    """Test the async_setup function."""

    result = asyncio.run(async_setup(mock_hass, {}))
    assert result is True


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_setup_entry(hass, monkeypatch):
    """The entry is set up with a coordinator, and the platforms are forwarded."""
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
    monkeypatch.setattr(
        AfvalwijzerDataUpdateCoordinator, "async_request_refresh", AsyncMock()
    )
    forward = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", forward)

    assert await async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator.config[CONF_HOUSE_NUMBER] == "1"
    forward.assert_awaited_once_with(entry, PLATFORMS)

    # Run the unload callbacks so the midnight timer doesn't linger after the test
    await entry._async_process_on_unload(hass)
    await hass.async_block_till_done()


def test_domain_constant():
    """Test that DOMAIN constant is properly defined."""

    assert DOMAIN == "afvalwijzer"


def test_platforms_list():
    """Test that PLATFORMS is properly defined."""
    assert isinstance(PLATFORMS, list)


def test_config_schema_exists():
    """Test that CONFIG_SCHEMA is defined."""
    assert CONFIG_SCHEMA is not None


def test_validate_required_config_accepts_a_complete_config():
    """A config with collector, postal code and house number passes."""
    _validate_required_config(
        {CONF_COLLECTOR: "circulus", CONF_POSTAL_CODE: "1234AB", CONF_HOUSE_NUMBER: "1"}
    )


@pytest.mark.parametrize(
    ("data", "missing"),
    [
        (
            {
                CONF_COLLECTOR: "circulus",
                CONF_POSTAL_CODE: "1234AB",
                CONF_HOUSE_NUMBER: "",
            },
            "house_number",
        ),
        (
            {
                CONF_COLLECTOR: "circulus",
                CONF_POSTAL_CODE: "1234AB",
                CONF_HOUSE_NUMBER: "  ",
            },
            "house_number",
        ),
        ({CONF_COLLECTOR: "circulus", CONF_POSTAL_CODE: "1234AB"}, CONF_HOUSE_NUMBER),
        (
            {
                CONF_COLLECTOR: "circulus",
                CONF_POSTAL_CODE: None,
                CONF_HOUSE_NUMBER: "1",
            },
            "postal_code",
        ),
        (
            {CONF_COLLECTOR: "", CONF_POSTAL_CODE: "1234AB", CONF_HOUSE_NUMBER: "1"},
            CONF_COLLECTOR,
        ),
    ],
)
def test_validate_required_config_names_the_missing_field(data, missing):
    """The error says which field to fill in again."""
    with pytest.raises(ConfigEntryError, match=missing):
        _validate_required_config(data)


def test_validate_required_config_lists_every_missing_field():
    """All missing fields are reported at once."""
    with pytest.raises(ConfigEntryError) as err:
        _validate_required_config({CONF_COLLECTOR: "circulus"})

    assert CONF_POSTAL_CODE in str(err.value)
    assert CONF_HOUSE_NUMBER in str(err.value)
    assert "reconfigure" in str(err.value)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_setup_fails_with_a_clear_error_when_house_number_is_empty(
    hass, monkeypatch
):
    """Home Assistant reports a setup error instead of querying the provider."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "circulus",
            CONF_POSTAL_CODE: "7300AA",
            CONF_HOUSE_NUMBER: "",
            CONF_SUFFIX: "",
        },
        options={},
    )
    entry.add_to_hass(hass)
    load_cache = AsyncMock(return_value=False)
    monkeypatch.setattr(
        AfvalwijzerDataUpdateCoordinator, "async_load_cache", load_cache
    )

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert CONF_HOUSE_NUMBER in entry.reason
    load_cache.assert_not_awaited()
