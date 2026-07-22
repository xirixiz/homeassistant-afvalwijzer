"""Tests for ProviderSensor behavior."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

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
from homeassistant.util import dt as dt_util


class FakeCoordinator:
    """Fake coordinator providing provider and notification data for tests."""

    def __init__(self, provider_data=None, notifications=None):
        """Initialize with optional provider and notifications payloads."""
        self.waste_data_with_today = provider_data or {}
        self.waste_data_without_today = provider_data or {}
        self.waste_data_custom = {}
        self.notification_data = notifications or []
        self.data = {}

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


def test_notification_sensor_counts_and_icon():
    """Provider notification sensor exposes count and list of notifications."""
    coordinator = FakeCoordinator(provider_data={}, notifications=["a", "b", "c"])
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = ProviderSensor(hass, "notifications", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

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

    sensor = ProviderSensor(
        SimpleNamespace(data={}), "restafval", FakeCoordinator(), cfg
    )
    assert sensor._cfg.include_today is False


def test_provider_sensor_timestamp_and_days_until():
    """Provider sensor returns timestamp and correct days-until value."""
    today = dt_util.now().date()
    target = today + timedelta(days=1)

    coordinator = FakeCoordinator(provider_data={"restafval": target}, notifications=[])
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
        # include_today resolved by default settings in ProviderSensor
    }

    sensor = ProviderSensor(hass, "restafval", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert isinstance(sensor.native_value, datetime)
    attrs = sensor.extra_state_attributes
    assert ATTR_DAYS_UNTIL_COLLECTION_DATE in attrs
    assert attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] == 1


async def test_added_to_hass_populates_initial_state():
    """Adding the sensor applies data the coordinator already holds.

    This replaces the old `update_before_add=True` behavior; without it a
    sensor added after a cache load would show the default label until the
    next refresh.
    """
    today = dt_util.now().date()
    target = today + timedelta(days=1)

    coordinator = FakeCoordinator(provider_data={"restafval": target})
    coordinator.data = {"waste_data_with_today": {"restafval": target}}

    sensor = ProviderSensor(
        _make_hass(),
        "restafval",
        coordinator,
        {
            CONF_COLLECTOR: "mijnafvalwijzer",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_SUFFIX: "",
            CONF_DEFAULT_LABEL: "geen",
        },
    )
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    assert isinstance(sensor.native_value, datetime)
    sensor.async_write_ha_state.assert_called()


async def test_added_to_hass_without_data_keeps_default():
    """Without coordinator data no premature state is written."""
    coordinator = FakeCoordinator()
    coordinator.data = None

    sensor = ProviderSensor(
        _make_hass(),
        "restafval",
        coordinator,
        {
            CONF_COLLECTOR: "mijnafvalwijzer",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_SUFFIX: "",
            CONF_DEFAULT_LABEL: "geen",
        },
    )
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    assert sensor.native_value == "geen"
    sensor.async_write_ha_state.assert_not_called()
