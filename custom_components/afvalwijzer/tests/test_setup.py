"""Test basic integration setup."""

import asyncio
import os
from unittest.mock import MagicMock

from custom_components.afvalwijzer import (
    CONFIG_SCHEMA,
    PLATFORMS,
    _skip_runtime_setup,
    async_setup,
    async_setup_entry,
)
from custom_components.afvalwijzer.const.const import DOMAIN


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
