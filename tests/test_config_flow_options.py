"""Flow-level tests for the options flow."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_ENABLE_CALENDAR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
    DEFAULT_ENABLE_CALENDAR,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "mijnafvalwijzer",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_SUFFIX: "",
        },
        unique_id="mijnafvalwijzer:1234AB:1",
    )


async def test_options_flow_enable_calendar_defaults_to_enabled(hass):
    """The options form offers enable_calendar, defaulting to today's behavior (on)."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["data_schema"]({})[CONF_ENABLE_CALENDAR] is DEFAULT_ENABLE_CALENDAR


async def test_options_flow_persists_enable_calendar_toggle(hass):
    """Submitting enable_calendar=False through the real options flow persists it."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_CALENDAR: False},
    )

    assert result["type"] == "create_entry"
    assert entry.options[CONF_ENABLE_CALENDAR] is False
