"""Test translation logic for sensors."""

import pytest

from custom_components.afvalwijzer.sensor_custom import CustomSensor
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

    class DummySensor:
        _config = {"translate_states": True}

    sensor = DummySensor()
    sensor.coordinator = coordinator
    translate_fn = CustomSensor._translate_value.__get__(sensor)

    # 1. Test single valid translation
    assert translate_fn("gft") == "Organic waste"

    # 2. Test fallback 'geen'
    assert translate_fn("geen") == "None"

    # 3. Test uppercase normalization
    assert translate_fn("GFT") == "Organic waste"

    # 4. Test comma separated
    assert translate_fn("gft, papier") == "Organic waste, Paper"
    assert translate_fn("gft,papier") == "Organic waste, Paper"

    # 5. Test unknown translation returns original
    assert translate_fn("unknown_type") == "unknown_type"

    # 6. Test date string is left intact
    assert translate_fn("2024-01-01") == "2024-01-01"

    # 7. Test None is ignored
    assert translate_fn(None) is None

    # 8. Test disabled translation
    sensor._config = {"translate_states": False}
    assert translate_fn("gft, papier") == "gft, papier"
    assert translate_fn("geen") == "geen"


@pytest.mark.asyncio
async def test_provider_sensor_fallback_translation():
    """Test that provider sensor translates its fallback state."""
    mock_translations = {
        "geen": {"name": "None"},
    }

    class DummyConfig:
        translate_states = True
        default_label = "geen"

    class DummyProviderSensor:
        _cfg = DummyConfig()

    sensor = DummyProviderSensor()
    sensor.coordinator = MockCoordinator(mock_translations)
    translate_fn = ProviderSensor._translate_value.__get__(sensor)

    assert translate_fn("geen") == "None"
    assert translate_fn("0") == "0"
