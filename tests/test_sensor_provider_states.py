"""Tests for how ProviderSensor turns coordinator data into a state."""

from datetime import date, datetime, timedelta
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.afvalwijzer.const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_HOUSE_NUMBER,
    CONF_INCLUDE_TODAY,
    CONF_POSTAL_CODE,
    CONF_SHOW_FULL_TIMESTAMP,
    SENSOR_ICON,
)
from custom_components.afvalwijzer.sensor_provider import ProviderSensor
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.util import dt as dt_util

CONFIG = {
    CONF_COLLECTOR: "mijnafvalwijzer",
    CONF_POSTAL_CODE: "1234AB",
    CONF_HOUSE_NUMBER: "1",
    CONF_DEFAULT_LABEL: "geen",
}


class _Coordinator:
    def __init__(self, with_today=None, without_today=None, notifications=None):
        self.waste_data_with_today = with_today
        self.waste_data_without_today = without_today
        self.notification_data = notifications
        self.data = {}
        self.last_update_success = True

    def async_add_listener(self, *_args, **_kwargs):
        return lambda: None


def _sensor(waste_type="gft", coordinator=None, **config):
    sensor = ProviderSensor(
        SimpleNamespace(),
        waste_type,
        coordinator or _Coordinator(),
        {**CONFIG, **config},
    )
    sensor.async_write_ha_state = MagicMock()
    return sensor


def _in_days(days):
    return dt_util.now().date() + timedelta(days=days)


# --- icons and the include-today setting -------------------------------------------


def test_an_unknown_waste_type_gets_the_generic_icon():
    """Types without an icon of their own use the recycle icon."""
    assert _sensor("not_a_type").icon == SENSOR_ICON
    assert _sensor("gft").icon != SENSOR_ICON


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({CONF_INCLUDE_TODAY: True}, True),
        ({CONF_INCLUDE_TODAY: False}, False),
        ({CONF_INCLUDE_TODAY: True, CONF_EXCLUDE_PICKUP_TODAY: "true"}, True),
        ({CONF_EXCLUDE_PICKUP_TODAY: "false"}, True),
        ({CONF_EXCLUDE_PICKUP_TODAY: "true"}, False),
        ({}, False),
    ],
)
def test_include_today_prefers_the_option_over_the_legacy_setting(config, expected):
    """The option wins; entries without it use the old exclude-today flag."""
    assert ProviderSensor._resolve_include_today(config) is expected


def test_the_sensor_reads_the_data_that_matches_the_setting():
    """With today included the with-today data is used, else the other."""
    coordinator = _Coordinator({"gft": _in_days(0)}, {"gft": _in_days(7)})
    included = _sensor(coordinator=coordinator, **{CONF_INCLUDE_TODAY: True})
    excluded = _sensor(coordinator=coordinator, **{CONF_INCLUDE_TODAY: False})

    included._handle_coordinator_update()
    excluded._handle_coordinator_update()

    assert included.extra_state_attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 0
    assert excluded.extra_state_attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 7


# --- values and the day flags -------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "today", "tomorrow", "day_after"),
    [
        (0, True, False, False),
        (1, False, True, False),
        (2, False, False, True),
        (3, False, False, False),
    ],
)
def test_the_day_flags_follow_the_collection_date(days, today, tomorrow, day_after):
    """The attributes tell whether the pickup is today, tomorrow or the day after."""
    sensor = _sensor(
        coordinator=_Coordinator({"gft": _in_days(days)}, {"gft": _in_days(days)}),
        **{CONF_INCLUDE_TODAY: True},
    )

    sensor._handle_coordinator_update()

    attributes = sensor.extra_state_attributes
    assert attributes[ATTR_IS_COLLECTION_DATE_TODAY] is today
    assert attributes[ATTR_IS_COLLECTION_DATE_TOMORROW] is tomorrow
    assert attributes[ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW] is day_after
    assert attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] == days
    assert sensor.device_class == SensorDeviceClass.TIMESTAMP


def test_without_full_timestamp_the_state_is_the_date_text():
    """With the option off the state is the ISO date, still with its flags."""
    target = _in_days(1)
    sensor = _sensor(
        coordinator=_Coordinator({"gft": target}, {"gft": target}),
        **{CONF_INCLUDE_TODAY: True, CONF_SHOW_FULL_TIMESTAMP: False},
    )

    sensor._handle_coordinator_update()

    assert sensor.device_class is None
    assert sensor.native_value == target.isoformat()
    assert sensor.extra_state_attributes[ATTR_IS_COLLECTION_DATE_TOMORROW] is True


@pytest.mark.parametrize(
    "value", [datetime(2099, 1, 5), "2099-01-05", date(2099, 1, 5)]
)
def test_dates_in_any_form_become_a_timestamp(value):
    """Dates, datetimes and their text all end up as a timestamp."""
    sensor = _sensor(coordinator=_Coordinator({"gft": value}, {"gft": value}))

    sensor._handle_coordinator_update()

    assert sensor.device_class == SensorDeviceClass.TIMESTAMP
    assert sensor.native_value.year == 2099


def test_a_value_that_is_no_date_is_shown_as_text_and_clears_the_flags():
    """Text is kept; the day flags of an earlier date are cleared."""
    coordinator = _Coordinator({"gft": _in_days(0)}, {"gft": _in_days(0)})
    sensor = _sensor(coordinator=coordinator, **{CONF_INCLUDE_TODAY: True})
    sensor._handle_coordinator_update()
    coordinator.waste_data_with_today = {"gft": "geen"}

    sensor._handle_coordinator_update()

    assert sensor.native_value == "geen"
    assert sensor.device_class is None
    attributes = sensor.extra_state_attributes
    assert attributes[ATTR_IS_COLLECTION_DATE_TODAY] is False
    assert attributes[ATTR_DAYS_UNTIL_COLLECTION_DATE] is None


# --- errors ------------------------------------------------------------------------


@pytest.mark.parametrize("data", [None, {}, {"papier": date(2099, 1, 5)}])
def test_missing_data_shows_the_default_label(data, caplog):
    """No data for the type is logged and shown as the label."""
    sensor = _sensor(coordinator=_Coordinator(data, data))

    with caplog.at_level(logging.ERROR):
        sensor._handle_coordinator_update()

    assert sensor.native_value == "geen"
    assert "No data for waste type: gft" in caplog.text
    assert sensor.extra_state_attributes[ATTR_IS_COLLECTION_DATE_TODAY] is False
    sensor.async_write_ha_state.assert_called_once()


def test_an_error_resets_the_state_of_an_earlier_date():
    """After an error nothing of the earlier date remains."""
    target = _in_days(1)
    coordinator = _Coordinator({"gft": target}, {"gft": target})
    sensor = _sensor(coordinator=coordinator, **{CONF_INCLUDE_TODAY: True})
    sensor._handle_coordinator_update()
    coordinator.waste_data_with_today = {}

    sensor._handle_coordinator_update()

    assert sensor.native_value == "geen"
    assert sensor.device_class is None
    assert sensor.extra_state_attributes[ATTR_IS_COLLECTION_DATE_TOMORROW] is False


# --- notifications -----------------------------------------------------------------


def test_the_notification_sensor_counts_and_changes_its_icon():
    """No notifications is a plain bell, some is an alert bell."""
    coordinator = _Coordinator(notifications=[])
    sensor = _sensor("notifications", coordinator)
    sensor._handle_coordinator_update()
    quiet = (sensor.native_value, sensor.icon)

    coordinator.notification_data = [{"title": "Storing"}, {"title": "Feestdagen"}]
    sensor._handle_coordinator_update()

    assert quiet == (0, "mdi:bell")
    assert (sensor.native_value, sensor.icon) == (2, "mdi:bell-alert")
    assert sensor.extra_state_attributes["count"] == 2
    assert (
        sensor.extra_state_attributes["notifications"] == coordinator.notification_data
    )


def test_the_notification_sensor_without_a_list_counts_zero():
    """A coordinator without notifications means none."""
    sensor = _sensor("notifications", _Coordinator(notifications=None))

    sensor._handle_coordinator_update()

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes["count"] == 0


def test_a_failing_notification_update_resets_to_zero(caplog):
    """An error while counting leaves a count of zero, never the label."""
    coordinator = _Coordinator(notifications=[{"title": "x"}])
    sensor = _sensor("notifications", coordinator)
    sensor._handle_coordinator_update()
    coordinator.notification_data = 5

    with caplog.at_level(logging.ERROR):
        sensor._handle_coordinator_update()

    assert sensor.native_value == 0
    assert sensor._fallback_state == "0"
    assert "Error updating sensor" in caplog.text
