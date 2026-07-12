"""Tests for sensor.py setup and behavior."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_SUFFIX,
    DOMAIN,
)
from custom_components.afvalwijzer.sensor import (
    _setup_sensors,
    async_setup_entry,
    async_setup_platform,
)
from custom_components.afvalwijzer.sensor_custom import CustomSensor
from custom_components.afvalwijzer.sensor_provider import ProviderSensor


class _FakeCoordinator:
    def __init__(self):
        today = date.today()
        self.waste_data_with_today = {"restafval": today}
        self.waste_data_without_today = {"restafval": today}
        self.waste_data_custom = {"next_date": today + timedelta(days=1)}
        self.notification_data = ["fake_notification"]
        self.data = {}
        self.config = {}

    def async_add_listener(self, cb):
        return lambda: None


def _make_hass():
    async def _exec(fn, *a, **k):
        return fn(*a, **k)

    hass = SimpleNamespace()
    hass.data = {}
    hass.async_add_executor_job = _exec

    # Mock task scheduling and config flow init
    hass.async_create_task = MagicMock()
    hass.config_entries = SimpleNamespace()
    hass.config_entries.flow = SimpleNamespace()
    hass.config_entries.flow.async_init = MagicMock()

    return hass


async def test_setup_sensors_creates_entities_and_notification_added():
    """Setup creates provider, custom, and notification entities."""
    hass = _make_hass()
    coordinator = _FakeCoordinator()

    added = []

    def _add_entities(entities, update):
        added.extend(entities)

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    await _setup_sensors(hass, cfg, _add_entities, coordinator)

    # One ProviderSensor (restafval), one CustomSensor (next_date), and notifications sensor
    assert len(added) == 3
    assert isinstance(added[0], ProviderSensor)
    assert isinstance(added[1], CustomSensor)
    assert isinstance(added[2], ProviderSensor)
    assert added[2].waste_type == "notifications"


async def test_async_setup_platform_triggers_import():
    """Legacy YAML setup triggers a config flow import."""
    hass = _make_hass()

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
    }

    await async_setup_platform(hass, cfg, MagicMock())

    # Verify the config flow init was called
    hass.config_entries.flow.async_init.assert_called_once_with(
        DOMAIN,
        context={"source": "import"},
        data=cfg,
    )
    hass.async_create_task.assert_called_once()


async def test_async_setup_entry_uses_coordinator():
    """async_setup_entry correctly retrieves the coordinator and calls _setup_sensors."""
    hass = _make_hass()
    coordinator = _FakeCoordinator()

    entry = SimpleNamespace()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
    }
    entry.options = {}

    hass.data[DOMAIN] = {"test_entry": {"coordinator": coordinator}}

    added = []

    def _add_entities(entities, update):
        added.extend(entities)

    await async_setup_entry(hass, entry, _add_entities)

    assert len(added) == 3
