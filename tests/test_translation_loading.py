"""Tests for _load_sensor_translations in __init__.py."""

from custom_components.afvalwijzer import _load_sensor_translations


def test_loads_nl_translations():
    """The Dutch translation file loads and contains known waste type keys."""
    translations = _load_sensor_translations("nl")
    assert translations["restafval"]["name"] == "Restafval"
    assert translations["gft"]["name"] == "GFT"


def test_loads_en_translations():
    """The English translation file loads and contains known waste type keys."""
    translations = _load_sensor_translations("en")
    assert translations["restafval"]["name"] == "Residual waste"
    assert translations["gft"]["name"] == "Organic waste (GFT)"


def test_unsupported_language_falls_back_to_english():
    """A language we don't ship a file for falls back to English, not an error."""
    translations = _load_sensor_translations("de")
    assert translations["restafval"]["name"] == "Residual waste"


def test_provider_sensor_state_translations_present():
    """Provider waste-type keys carry a 'state' translation for the default label.

    This is what lets enum device_class translate the fallback text while the
    sensor's actual state/native_value stays the raw default_label.
    """
    translations = _load_sensor_translations("nl")
    assert translations["restafval"]["state"]["geen"] == "Geen"
