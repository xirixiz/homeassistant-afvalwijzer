"""Tests for ProviderSensor behavior."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockEntityPlatform

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
from homeassistant.components.sensor import SensorDeviceClass
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


def test_device_class_clears_when_switching_from_default_label_to_timestamp():
    """device_class set during a default_label fallback doesn't leak into a later timestamp update."""
    today = dt_util.now().date()
    target = today + timedelta(days=1)

    coordinator = FakeCoordinator(provider_data={"restafval": "geen"})
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = ProviderSensor(hass, "restafval", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()
    assert sensor._attr_device_class is None

    # A pickup date now appears on a later refresh.
    coordinator.waste_data_with_today = {"restafval": target}
    coordinator.waste_data_without_today = {"restafval": target}
    sensor._handle_coordinator_update()

    assert isinstance(sensor.native_value, datetime)
    assert sensor._attr_device_class == SensorDeviceClass.TIMESTAMP


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


def test_default_label_fallback_state():
    """When nothing is scheduled, state stays the raw default_label."""
    coordinator = FakeCoordinator(provider_data={"restafval": "geen"})
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    sensor = ProviderSensor(hass, "restafval", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert sensor.native_value == "geen"
    assert sensor._attr_device_class is None


def test_custom_default_label_fallback_state():
    """A custom default_label is reported as-is when nothing is scheduled."""
    coordinator = FakeCoordinator(provider_data={"restafval": "nothing scheduled"})
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "nothing scheduled",
    }

    sensor = ProviderSensor(hass, "restafval", coordinator, cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert sensor.native_value == "nothing scheduled"
    assert sensor._attr_device_class is None


def test_error_state_has_no_device_class_for_non_notification_sensor():
    """An error falling back to default_label carries no device_class."""
    hass = _make_hass()
    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    # No data at all for this waste type -> _handle_coordinator_update raises
    # internally and falls back to _set_error_state.
    sensor = ProviderSensor(hass, "restafval", FakeCoordinator(), cfg)
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    assert sensor.native_value == "geen"
    assert sensor._attr_device_class is None


def test_notification_sensor_never_gets_a_device_class():
    """The notifications sensor is a count, never a classed text sensor."""
    coordinator = FakeCoordinator(notifications=[])
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

    assert sensor._attr_device_class is None


async def test_default_label_state_survives_real_ha_validation(hass):
    """The default_label fallback state passes HA's real SensorEntity.state check.

    Registers through a real entity platform so state/device_class run
    through HA's own validation, rather than only reading the attributes
    off a bare instance.
    """
    coordinator = FakeCoordinator(provider_data={"restafval": "geen"})
    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }
    sensor = ProviderSensor(hass, "restafval", coordinator, cfg)

    platform = MockEntityPlatform(hass, domain="sensor")
    await platform.async_add_entities([sensor])
    sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    assert hass.states.get(sensor.entity_id).state == "geen"


async def test_timestamp_state_survives_real_ha_validation(hass):
    """A scheduled pickup date passes HA's real SensorEntity.state check."""
    target = dt_util.now().date() + timedelta(days=1)
    coordinator = FakeCoordinator(provider_data={"restafval": target})
    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }
    sensor = ProviderSensor(hass, "restafval", coordinator, cfg)

    platform = MockEntityPlatform(hass, domain="sensor")
    await platform.async_add_entities([sensor])
    sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    state = hass.states.get(sensor.entity_id)
    assert state.state not in (None, "unknown", "unavailable")
    assert dt_util.parse_datetime(state.state) is not None
