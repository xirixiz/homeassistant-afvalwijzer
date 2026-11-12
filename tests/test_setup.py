"""Test basic integration setup."""

import asyncio
import os
from unittest.mock import MagicMock

import pytest

from custom_components.afvalwijzer import (
    CONFIG_SCHEMA,
    PLATFORMS,
    _skip_runtime_setup,
    _validate_required_config,
    async_setup,
    async_setup_entry,
)
from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    DOMAIN,
)
from homeassistant.exceptions import ConfigEntryError


def test_async_setup(mock_hass):
    """Test the async_setup function."""

    result = asyncio.run(async_setup(mock_hass, {}))
    assert result is True


def test_async_setup_entry(mock_hass):
    """Test the async_setup_entry function."""

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "collector": "mijnafvalwijzer",
        "postal_code": "1234AB",
        "house_number": "1",
    }

    result = asyncio.run(async_setup_entry(mock_hass, entry))
    assert result is True


def test_domain_constant():
    """Test that DOMAIN constant is properly defined."""

    assert DOMAIN == "afvalwijzer"


def test_platforms_list():
    """Test that PLATFORMS is properly defined."""
    assert isinstance(PLATFORMS, list)


def test_config_schema_exists():
    """Test that CONFIG_SCHEMA is defined."""
    assert CONFIG_SCHEMA is not None


def test_skip_runtime_setup():
    """Test that runtime setup can be skipped in test mode."""

    assert os.getenv("AFVALWIJZER_SKIP_INIT") == "1"
    assert _skip_runtime_setup() is True


def _entry(data):
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = data
    entry.options = {}
    return entry


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


def test_setup_entry_fails_before_fetching_when_house_number_is_empty(
    mock_hass, monkeypatch
):
    """The setup stops with a ConfigEntryError instead of querying the provider."""
    monkeypatch.setenv("AFVALWIJZER_SKIP_INIT", "0")
    entry = _entry(
        {CONF_COLLECTOR: "circulus", CONF_POSTAL_CODE: "7300AA", CONF_HOUSE_NUMBER: ""}
    )

    with pytest.raises(ConfigEntryError, match=CONF_HOUSE_NUMBER):
        asyncio.run(async_setup_entry(mock_hass, entry))

    assert DOMAIN not in mock_hass.data or entry.entry_id not in mock_hass.data[DOMAIN]
