"""Test translation logic for sensors."""

import pytest

from custom_components.afvalwijzer.common.sensor_utils import translate_value
from custom_components.afvalwijzer.sensor_provider import ProviderSensor


class MockCoordinator:
    """Mock coordinator for testing."""

    def __init__(self, translations):
        """Initialize the mock coordinator."""
        self.sensor_translations = translations


@pytest.mark.asyncio
async def test_translate_value():
    """Test the translation of various string values."""
    mock_translations = {
        "gft": {"name": "Organic waste"},
        "papier": {"name": "Paper"},
        "geen": {"name": "None"},
        "restafval": {"name": "Residual waste"},
    }

    coordinator = MockCoordinator(mock_translations)
    config_enabled = {"translate_states": True}
    config_disabled = {"translate_states": False}

    # 1. Test single valid translation
    assert translate_value("gft", config_enabled, coordinator) == "Organic waste"

    # 2. Test fallback 'geen'
    assert translate_value("geen", config_enabled, coordinator) == "None"

    # 3. Test uppercase normalization
    assert translate_value("GFT", config_enabled, coordinator) == "Organic waste"

    # 4. Test comma separated
    assert (
        translate_value("gft, papier", config_enabled, coordinator)
        == "Organic waste, Paper"
    )
    assert (
        translate_value("gft,papier", config_enabled, coordinator)
        == "Organic waste, Paper"
    )

    # 5. Test unknown translation returns original
    assert (
        translate_value("unknown_type", config_enabled, coordinator) == "unknown_type"
    )

    # 6. Test date string is left intact
    assert translate_value("2024-01-01", config_enabled, coordinator) == "2024-01-01"

    # 7. Test None is ignored
    assert translate_value(None, config_enabled, coordinator) is None

    # 8. Test disabled translation
    assert translate_value("gft, papier", config_disabled, coordinator) == "gft, papier"
    assert translate_value("geen", config_disabled, coordinator) == "geen"


@pytest.mark.asyncio
async def test_provider_sensor_fallback_translation():
    """Test that provider sensor translates its fallback state."""
    mock_translations = {
        "geen": {"name": "None"},
    }

    class DummyProviderSensor:
        _config = {"translate_states": True}

    sensor = DummyProviderSensor()
    sensor.coordinator = MockCoordinator(mock_translations)
    translate_fn = ProviderSensor._translate_value.__get__(sensor)

    assert translate_fn("geen") == "None"
    assert translate_fn("0") == "0"
