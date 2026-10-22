"""Tests for the collector selection in the config flow."""

from custom_components.afvalwijzer.config_flow import (
    ALL_COLLECTORS,
    COLLECTOR_CHOICES,
    _collector_selector,
    _reconfigure_schema_for,
)
from custom_components.afvalwijzer.const.const import (
    COLLECTOR_LABELS,
    CONF_COLLECTOR,
)


def test_every_collector_has_a_label():
    """Each selectable collector has a display name."""
    assert set(ALL_COLLECTORS) - set(COLLECTOR_LABELS) == set()


def test_no_label_without_collector():
    """Labels for collectors that no longer exist are removed."""
    assert set(COLLECTOR_LABELS) - set(ALL_COLLECTORS) == set()


def test_selector_is_searchable_and_shows_the_display_text():
    """The dropdown allows typing (that is what enables search) and shows readable text."""
    config = _collector_selector().config

    assert config["custom_value"] is True
    assert config["multiple"] is False
    assert all(option["value"] == option["label"] for option in config["options"])
    assert {option["value"] for option in config["options"]} == set(COLLECTOR_CHOICES)


def test_every_collector_is_offered_under_its_display_name():
    """All collectors stay selectable."""
    assert {COLLECTOR_CHOICES[COLLECTOR_LABELS[key]] for key in ALL_COLLECTORS} == set(
        ALL_COLLECTORS
    )
    assert COLLECTOR_CHOICES["Cyclus NV"] == "cyclus"
    assert COLLECTOR_CHOICES["Súdwest-Fryslân"] == "sudwestfryslan"


def test_reconfigure_schema_is_prefilled_with_the_display_name():
    """Reconfiguring shows the collector's display name, not its key."""
    schema = _reconfigure_schema_for({CONF_COLLECTOR: "omrin"})

    result = schema({"postal_code": "1234AB", "house_number": "1"})

    assert result[CONF_COLLECTOR] == "Omrin"
