"""Tests for how CustomSensor turns coordinator data into a state."""

from datetime import date, datetime
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.afvalwijzer.common import sensor_utils
from custom_components.afvalwijzer.const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SHOW_FULL_TIMESTAMP,
    SENSOR_ICON,
)
from custom_components.afvalwijzer.sensor_custom import CustomSensor
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.util import dt as dt_util

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
CONFIG = {
    CONF_COLLECTOR: "mijnafvalwijzer",
    CONF_POSTAL_CODE: "1234AB",
    CONF_HOUSE_NUMBER: "1",
    CONF_DEFAULT_LABEL: "geen",
}


class _Coordinator:
    def __init__(self, custom=None, data=None):
        self.waste_data_custom = custom
        self.data = data
        self.sensor_translations = {"gft": {"name": "GFT"}}
        self.last_update_success = True

    def async_add_listener(self, *_args, **_kwargs):
        return lambda: None


def _sensor(waste_type="next_date", custom=None, *, full_timestamp=True, data=None):
    config = {**CONFIG, CONF_SHOW_FULL_TIMESTAMP: full_timestamp}
    sensor = CustomSensor(
        SimpleNamespace(), waste_type, _Coordinator(custom, data), config
    )
    sensor.async_write_ha_state = MagicMock()
    return sensor


# --- icons -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("waste_type", "icon"),
    [
        ("today", "mdi:calendar-today"),
        ("tomorrow", "mdi:calendar"),
        ("day_after_tomorrow", "mdi:calendar-end"),
        ("next_date", "mdi:calendar-multiselect"),
        ("next_in_days", "mdi:counter"),
        ("next_type", "mdi:label-outline"),
        ("anything_else", SENSOR_ICON),
    ],
)
def test_each_custom_sensor_has_its_own_icon(waste_type, icon):
    """Every sensor kind has an icon; unknown kinds use the generic one."""
    assert _sensor(waste_type).icon == icon


@pytest.mark.parametrize(
    ("value", "expected_generic"),
    [
        ("gft", False),
        (" GFT ", False),
        ("gft, papier", True),
        ("geen", True),
        ("", True),
        (None, True),
        (5, True),
    ],
)
def test_next_type_icon_follows_a_single_known_type(value, expected_generic):
    """One known waste type gets its own icon; anything else the label icon."""
    icon = CustomSensor._next_type_icon(value)

    assert (icon == "mdi:label-outline") is expected_generic


def test_the_next_type_sensor_changes_its_icon_with_the_type():
    """The icon follows the data after each update."""
    sensor = _sensor("next_type", {"next_type": "gft"})
    sensor._handle_coordinator_update()
    single = sensor.icon

    sensor.coordinator.waste_data_custom = {"next_type": "gft, papier"}
    sensor._handle_coordinator_update()

    assert single == sensor_utils.icon_for_waste_type("gft")
    assert sensor.icon == "mdi:label-outline"


# --- values ------------------------------------------------------------------------


def test_a_date_is_a_timestamp_with_the_days_until_it():
    """A date value gives a timestamp at local midnight and the days left."""
    today = dt_util.now().date()
    target = date.fromordinal(today.toordinal() + 3)
    sensor = _sensor(custom={"next_date": target})

    sensor._handle_coordinator_update()

    assert sensor.device_class == SensorDeviceClass.TIMESTAMP
    assert sensor.native_value.date() == target
    assert sensor.extra_state_attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 3
    assert sensor.extra_state_attributes[ATTR_LAST_UPDATE] is not None
    sensor.async_write_ha_state.assert_called_once()


@pytest.mark.parametrize("text", ["2099-01-05", "2099-01-05T00:00:00"])
def test_a_date_as_text_is_parsed(text):
    """Text from a cache or a collector is parsed like a real date."""
    sensor = _sensor(custom={"next_date": text})

    sensor._handle_coordinator_update()

    assert sensor.device_class == SensorDeviceClass.TIMESTAMP
    assert sensor.native_value.year == 2099


def test_a_datetime_is_converted_through_utc():
    """A naive datetime is read in the Home Assistant time zone."""
    sensor = _sensor(custom={"next_date": datetime(2099, 1, 5, 0, 0)})

    sensor._handle_coordinator_update()

    assert sensor.native_value.astimezone(AMSTERDAM).date() == date(2099, 1, 5)


def test_without_full_timestamp_the_state_is_the_date_text():
    """With the option off the state is the ISO date and there is no device class."""
    sensor = _sensor(custom={"next_date": date(2099, 1, 5)}, full_timestamp=False)

    sensor._handle_coordinator_update()

    assert sensor.device_class is None
    assert sensor.native_value == "2099-01-05"
    assert sensor.extra_state_attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] is not None


@pytest.mark.parametrize("value", ["gft, papier", 7, "not a date"])
def test_other_values_are_shown_as_text(value):
    """Types and counts are shown as they are."""
    sensor = _sensor("next_type", {"next_type": value})

    sensor._handle_coordinator_update()

    assert sensor.native_value == str(value)
    assert sensor.device_class is None


def test_translated_types_are_listed_for_the_type_sensors():
    """The type sensors carry their types in the language of the user."""
    sensor = _sensor("today", {"today": "gft"})

    sensor._handle_coordinator_update()

    assert sensor.extra_state_attributes["translated_types"] == ["GFT"]
    assert "translated_types" not in _sensor("next_in_days").extra_state_attributes


def test_a_timestamp_without_a_datetime_has_no_native_value():
    """A timestamp sensor without a datetime reports nothing, not text."""
    sensor = _sensor()
    sensor._attr_device_class = SensorDeviceClass.TIMESTAMP
    sensor._native_value = "text"

    assert sensor.native_value is None


# --- errors ------------------------------------------------------------------------


@pytest.mark.parametrize("custom", [None, {}, {"other": "x"}])
def test_missing_data_shows_the_default_label(custom, caplog):
    """No data for the sensor is logged and shown as the label."""
    sensor = _sensor("next_type", custom)

    with caplog.at_level(logging.ERROR):
        sensor._handle_coordinator_update()

    assert sensor.native_value == "geen"
    assert sensor.icon == "mdi:label-outline"
    assert "No data for custom sensor: next_type" in caplog.text
    assert sensor.extra_state_attributes[ATTR_LAST_UPDATE] is not None
    sensor.async_write_ha_state.assert_called_once()


def test_an_error_resets_a_value_that_was_shown_before():
    """After an error the old date is gone."""
    sensor = _sensor(custom={"next_date": date(2099, 1, 5)})
    sensor._handle_coordinator_update()
    sensor.coordinator.waste_data_custom = {}

    sensor._handle_coordinator_update()

    assert sensor.device_class is None
    assert sensor.native_value == "geen"
    assert sensor.extra_state_attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] is None


# --- being added -------------------------------------------------------------------


async def test_a_sensor_added_with_data_shows_it_at_once(monkeypatch):
    """Data the coordinator already has is applied when the entity is added."""
    sensor = _sensor("next_type", {"next_type": "gft, papier"}, data={"x": 1})
    monkeypatch.setattr(
        "custom_components.afvalwijzer.sensor_custom.CoordinatorEntity.async_added_to_hass",
        AsyncMock(),
    )

    await sensor.async_added_to_hass()

    assert sensor.native_value == "gft, papier"


async def test_a_sensor_added_without_data_waits(monkeypatch):
    """With no data yet the sensor keeps its label until the first update."""
    sensor = _sensor("next_type", {"next_type": "gft"}, data=None)
    monkeypatch.setattr(
        "custom_components.afvalwijzer.sensor_custom.CoordinatorEntity.async_added_to_hass",
        AsyncMock(),
    )

    await sensor.async_added_to_hass()

    assert sensor.native_value == "geen"
    sensor.async_write_ha_state.assert_not_called()


def test_the_device_groups_the_sensors_of_an_address():
    """The sensor belongs to the device of its address."""
    sensor = _sensor()

    assert sensor.device_info["name"].startswith("Afvalwijzer")
    assert sensor.unique_id == sensor_utils.make_unique_id(CONFIG, "next_date")
