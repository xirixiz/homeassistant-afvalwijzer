"""Flow-level tests for the reconfigure step."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _entry(postal_code="1234AB", house_number="1", unique_id=None):
    data = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: postal_code,
        CONF_HOUSE_NUMBER: house_number,
        CONF_SUFFIX: "",
    }
    return MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id=unique_id or f"mijnafvalwijzer:{postal_code}:{house_number}",
    )


def _user_input(postal_code, house_number):
    return {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: postal_code,
        CONF_HOUSE_NUMBER: house_number,
        CONF_SUFFIX: "",
        CONF_FRIENDLY_NAME: "",
    }


async def test_reconfigure_to_new_address_updates_entry(hass):
    """Reconfiguring to a free address updates data and unique_id."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as reload_mock:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input("9999ZZ", "3")
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_POSTAL_CODE] == "9999ZZ"
    assert entry.data[CONF_HOUSE_NUMBER] == "3"
    assert entry.unique_id == "mijnafvalwijzer:9999ZZ:3"
    reload_mock.assert_awaited_once_with(entry.entry_id)


async def test_reconfigure_same_address_succeeds(hass):
    """Reconfiguring without changing the address does not self-collide."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input("1234AB", "1")
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "mijnafvalwijzer:1234AB:1"


async def test_reconfigure_to_existing_address_aborts(hass):
    """Reconfiguring to an address owned by another entry aborts.

    Regression test: this used to silently create a duplicate.
    """
    entry = _entry()
    entry.add_to_hass(hass)
    other = _entry(postal_code="5678CD", house_number="2")
    other.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input("5678CD", "2")
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    # Original entry is untouched
    assert entry.data[CONF_POSTAL_CODE] == "1234AB"
    assert entry.unique_id == "mijnafvalwijzer:1234AB:1"


async def test_reconfigure_invalid_postal_code_shows_error(hass):
    """An invalid postal code re-shows the form with an error."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input("INVALID", "1")
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_postal_code"}
    assert entry.data[CONF_POSTAL_CODE] == "1234AB"
