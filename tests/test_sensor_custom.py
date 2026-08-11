"""Tests for CustomSensor behavior."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockEntityPlatform

from custom_components.afvalwijzer.const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
)
from custom_components.afvalwijzer.sensor_custom import CustomSensor
from homeassistant.util import dt as dt_util


class FakeCoordinator:
    """Fake coordinator providing deterministic custom waste data for tests."""

    def __init__(self, value, sensor_translations=None):
        """Initialize with a single custom value for `next_date`."""
        self.waste_data_custom = {"next_date": value}
        self.waste_data_with_today = {}
        self.waste_data_without_today = {}
        self.notification_data = []
        self.data = {}
        self.sensor_translations = sensor_translations or {}
        self.last_update_success = True

    def async_add_listener(self, update_callback, context=None):
        """Mimic the coordinator listener registration."""
        return lambda: None


def _make_hass():
    async def _exec(fn, *a, **k):
        return fn(*a, **k)

    hass = SimpleNamespace()
    hass.data = {}
    hass.async_add_executor_job = _exec
    return hass


def test_custom_sensor_timestamp_and_days_until():
    """CustomSensor exposes timestamp and correct days-until attribute."""
    today = dt_util.now().date()
    target = today + timedelta(days=2)

    coordinator = FakeCoordinator(target)
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(hass, "next_date", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    # timestamp mode is enabled by default, native_value should be datetime
    assert isinstance(sensor.native_value, datetime)

    attrs = sensor.extra_state_attributes
    assert ATTR_DAYS_UNTIL_COLLECTION_DATE in attrs
    assert attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 2


def test_custom_sensor_fallback_when_no_full_timestamp():
    """CustomSensor returns ISO date string when full timestamp disabled."""
    today = date.today()
    target = today + timedelta(days=5)

    coordinator = FakeCoordinator(target)
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
        "show_full_timestamp": False,
    }

    sensor = CustomSensor(hass, "next_date", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    # when full timestamp disabled, native_value returns fallback string
    assert isinstance(sensor.native_value, str)
    assert sensor.native_value == target.isoformat()


def test_next_type_icon_follows_waste_type():
    """The next_type sensor icon matches the waste type it reports."""
    coordinator = FakeCoordinator(None)
    coordinator.waste_data_custom = {"next_type": "restafval"}

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(_make_hass(), "next_type", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()
    assert sensor.icon == "mdi:trash-can"

    # A single different type switches the icon
    coordinator.waste_data_custom = {"next_type": "gft"}
    sensor._handle_coordinator_update()
    assert sensor.icon == "mdi:flower"

    # Multiple types on the same date fall back to the generic label icon
    coordinator.waste_data_custom = {"next_type": "gft, papier"}
    sensor._handle_coordinator_update()
    assert sensor.icon == "mdi:label-outline"

    # Default label (no upcoming pickup) also falls back
    coordinator.waste_data_custom = {"next_type": "geen"}
    sensor._handle_coordinator_update()
    assert sensor.icon == "mdi:label-outline"


async def test_added_to_hass_populates_initial_state():
    """Adding the sensor applies data the coordinator already holds."""
    today = dt_util.now().date()
    target = today + timedelta(days=2)

    coordinator = FakeCoordinator(target)
    coordinator.data = {"waste_data_custom": {"next_date": target}}

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(_make_hass(), "next_date", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    assert isinstance(sensor.native_value, datetime)
    sensor.async_write_ha_state.assert_called()


def test_translated_types_excluded_from_recorder_history():
    """translated_types is declared unrecorded (it's language-derived, not state)."""
    assert CustomSensor._unrecorded_attributes == frozenset({"translated_types"})


def test_next_type_exposes_translated_types_attribute():
    """next_type carries a translated_types attribute alongside the raw state."""
    coordinator = FakeCoordinator(
        None, sensor_translations={"gft": {"name": "GFT"}, "pmd": {"name": "PMD"}}
    )
    coordinator.waste_data_custom = {"next_type": "gft, pmd"}

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(_make_hass(), "next_type", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    # The state itself stays raw and untranslated.
    assert sensor.native_value == "gft, pmd"
    assert sensor.extra_state_attributes["translated_types"] == ["GFT", "PMD"]


def test_translated_types_keeps_custom_default_label_with_comma_whole():
    """A custom default_label containing a comma isn't fragmented into bogus types.

    default_label is free text a user configures, not a list of waste
    types - when nothing is scheduled, the raw fallback state must match
    what translated_types reports.
    """
    label = "Niets gepland, geen"
    coordinator = FakeCoordinator(None, sensor_translations={})
    coordinator.waste_data_custom = {"today": label}

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: label,
    }

    sensor = CustomSensor(_make_hass(), "today", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert sensor.native_value == label
    assert sensor.extra_state_attributes["translated_types"] == [label]


async def test_comma_default_label_survives_real_ha_validation(hass):
    """The comma-in-default_label fix holds through HA's real entity lifecycle.

    Registers through a real entity platform so state/attributes run
    through HA's own validation, rather than only reading them off a bare
    instance.
    """
    label = "Niets gepland, geen"
    coordinator = FakeCoordinator(None, sensor_translations={})
    coordinator.waste_data_custom = {"today": label}

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: label,
    }

    sensor = CustomSensor(hass, "today", coordinator, cfg)

    platform = MockEntityPlatform(hass, domain="sensor")
    await platform.async_add_entities([sensor])
    sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    state = hass.states.get(sensor.entity_id)
    assert state.state == label
    assert state.attributes["translated_types"] == [label]


def test_translated_types_falls_back_to_raw_when_unmapped():
    """Unknown waste types fall back to their original (untranslated) text."""
    coordinator = FakeCoordinator(None, sensor_translations={})
    coordinator.waste_data_custom = {"today": "some_unmapped_type"}

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(_make_hass(), "today", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert sensor.extra_state_attributes["translated_types"] == ["some_unmapped_type"]


def test_next_date_has_no_translated_types_attribute():
    """Date/count sensors (next_date, next_in_days) don't get translated_types."""
    today = date.today()
    coordinator = FakeCoordinator(today + timedelta(days=1))

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(_make_hass(), "next_date", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert "translated_types" not in sensor.extra_state_attributes
