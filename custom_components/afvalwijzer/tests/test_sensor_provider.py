"""Tests for ProviderSensor behavior."""

import asyncio
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from custom_components.afvalwijzer.const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
)
from custom_components.afvalwijzer.sensor_provider import ProviderSensor


class FakeFetch:
    """Fake fetcher providing provider and notification data for tests."""

    def __init__(self, provider_data=None, notifications=None):
        """Initialize with optional provider and notifications payloads."""
        self.waste_data_with_today = provider_data or {}
        self.waste_data_without_today = provider_data or {}
        self.waste_data_custom = {}
        self.notification_data = notifications or []

    def update(self):
        """No-op update method to match the production interface."""
        return None


def _make_hass():
    async def _exec(fn, *a, **k):
        return fn(*a, **k)

    hass = SimpleNamespace()
    hass.data = {}
    hass.async_add_executor_job = _exec
    return hass


def test_notification_sensor_counts_and_icon():
    """Provider notification sensor exposes count and list of notifications."""
    fetch = FakeFetch(provider_data={}, notifications=["a", "b", "c"])
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = ProviderSensor(hass, "notifications", fetch, cfg)

    asyncio.run(sensor.async_update())

    assert sensor.native_value == 3
    attrs = sensor.extra_state_attributes
    assert attrs.get("count") == 3
    assert attrs.get("notifications") == ["a", "b", "c"]


def test_resolve_include_today_legacy_flag():
    """Legacy exclude flag resolves `include_today` to False."""
    # legacy config uses exclude_pickup_today; True means include_today should be False
    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
        CONF_EXCLUDE_PICKUP_TODAY: True,
    }

    sensor = ProviderSensor(SimpleNamespace(data={}), "restafval", FakeFetch(), cfg)
    assert sensor._cfg.include_today is False


def test_provider_sensor_timestamp_and_days_until():
    """Provider sensor returns timestamp and correct days-until value."""
    today = date.today()
    target = today + timedelta(days=1)

    fetch = FakeFetch(provider_data={"restafval": target}, notifications=[])
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
        # include_today resolved by default settings in ProviderSensor
    }

    sensor = ProviderSensor(hass, "restafval", fetch, cfg)
    asyncio.run(sensor.async_update())

    assert isinstance(sensor.native_value, datetime)
    attrs = sensor.extra_state_attributes
    assert ATTR_DAYS_UNTIL_COLLECTION_DATE in attrs
    assert attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 1
