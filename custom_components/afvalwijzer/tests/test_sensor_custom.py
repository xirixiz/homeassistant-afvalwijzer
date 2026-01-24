"""Tests for CustomSensor behavior."""

import asyncio
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from custom_components.afvalwijzer.const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
)
from custom_components.afvalwijzer.sensor_custom import CustomSensor


class FakeFetch:
    """Fake fetcher providing deterministic custom waste data for tests."""

    def __init__(self, value):
        """Initialize with a single custom value for `next_date`."""
        self.waste_data_custom = {"next_date": value}
        self.waste_data_with_today = {}
        self.waste_data_without_today = {}
        self.notification_data = []

    def update(self):
        """No-op update method to match the production interface."""
        # noop: data is already present
        return None


def _make_hass():
    async def _exec(fn, *a, **k):
        return fn(*a, **k)

    hass = SimpleNamespace()
    hass.data = {}
    hass.async_add_executor_job = _exec
    return hass


def test_custom_sensor_timestamp_and_days_until():
    """CustomSensor exposes timestamp and correct days-until attribute."""
    today = date.today()
    target = today + timedelta(days=2)

    fetch = FakeFetch(target)
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = CustomSensor(hass, "next_date", fetch, cfg)

    asyncio.run(sensor.async_update())

    # timestamp mode is enabled by default, native_value should be datetime
    assert isinstance(sensor.native_value, datetime)

    attrs = sensor.extra_state_attributes
    assert ATTR_DAYS_UNTIL_COLLECTION_DATE in attrs
    assert attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 2


def test_custom_sensor_fallback_when_no_full_timestamp():
    """CustomSensor returns ISO date string when full timestamp disabled."""
    today = date.today()
    target = today + timedelta(days=5)

    fetch = FakeFetch(target)
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
        "show_full_timestamp": False,
    }

    sensor = CustomSensor(hass, "next_date", fetch, cfg)

    asyncio.run(sensor.async_update())

    # when full timestamp disabled, native_value returns fallback string
    assert isinstance(sensor.native_value, str)
    assert sensor.native_value == target.isoformat()
