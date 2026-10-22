"""Tests for the collector selection in the config flow."""

import pytest
import voluptuous as vol

from custom_components.afvalwijzer.config_flow import (
    ALL_COLLECTORS,
    COLLECTOR_SCHEMA,
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


def test_selector_offers_exactly_the_collectors_and_no_custom_values():
    """The dropdown lists every collector and rejects anything else."""
    config = _collector_selector().config

    values = [option["value"] for option in config["options"]]
    assert set(ALL_COLLECTORS) <= set(values)
    assert config["custom_value"] is False
    assert config["multiple"] is False


def test_selector_labels_are_the_display_names():
    """Options carry the display name as label and the collector as value."""
    options = {
        option["value"]: option["label"]
        for option in _collector_selector().config["options"]
    }

    assert options["cyclus"] == "Cyclus NV"
    assert options["sudwestfryslan"] == "Súdwest-Fryslân"


def test_user_step_accepts_a_collector_and_rejects_unknown_ones():
    """The form validates the chosen value against the list."""
    assert COLLECTOR_SCHEMA({CONF_COLLECTOR: "cyclus"}) == {CONF_COLLECTOR: "cyclus"}
    with pytest.raises(vol.Invalid):
        COLLECTOR_SCHEMA({CONF_COLLECTOR: "not-a-collector"})


def test_reconfigure_schema_uses_the_same_selector():
    """Reconfiguring offers the same labelled dropdown, pre-filled."""
    schema = _reconfigure_schema_for({CONF_COLLECTOR: "omrin"})

    assert schema({"postal_code": "1234AB", "house_number": "1"})[CONF_COLLECTOR] == (
        "omrin"
    )
