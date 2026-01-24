"""Tests for sensor.py setup and behavior."""

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
)
from custom_components.afvalwijzer.sensor import (
    _setup_sensors,
    async_setup_entry,
)
from custom_components.afvalwijzer.sensor_custom import CustomSensor
from custom_components.afvalwijzer.sensor_provider import ProviderSensor


class _FakeData:
    def __init__(self):
        today = date.today()
        self.waste_data_with_today = {"restafval": today}
        self.waste_data_without_today = {"restafval": today}
        self.waste_data_custom = {"next_date": today + timedelta(days=1)}
        self.notification_data = []
        self._updates = 0

    def update(self):
        self._updates += 1
        return True, None


def _make_hass():
    class _Awaitable:
        def __init__(self, result):
            self._result = result

        def __await__(self):
            async def _wrap():
                return self._result

            return _wrap().__await__()

    def _exec(fn, *a, **k):
        # emulate HA by returning an awaitable
        result = fn(*a, **k)
        return _Awaitable(result)

    hass = SimpleNamespace()
    hass.data = {}
    hass.async_add_executor_job = _exec
    return hass


def test_setup_sensors_creates_entities_and_notification_added(monkeypatch):
    """Setup creates provider, custom, and notification entities and schedules updates."""
    hass = _make_hass()
    data = _FakeData()

    captured = {
        "entities": None,
        "callback": None,
        "interval": None,
    }

    def _track(_hass, cb, interval):
        captured["callback"] = cb
        captured["interval"] = interval

    # Patch the scheduler to capture the callback
    monkeypatch.setattr(
        "custom_components.afvalwijzer.sensor.async_track_time_interval", _track
    )

    added = []

    def _add_entities(entities, update):
        added.extend(entities)

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    asyncio.run(_setup_sensors(hass, cfg, _add_entities, data))

    # One ProviderSensor (restafval), one CustomSensor (next_date), and notifications sensor
    assert len(added) == 3
    assert isinstance(added[0], ProviderSensor)
    assert isinstance(added[1], CustomSensor)
    assert isinstance(added[2], ProviderSensor)

    # Ensure the scheduler was set up
    assert captured["callback"] is not None
    assert captured["interval"] is not None


def test_schedule_update_invokes_data_update(monkeypatch):
    """Scheduled callback triggers data.update via executor job."""
    hass = _make_hass()
    data = _FakeData()

    captured_cb = {"cb": None}

    def _track(_hass, cb, _interval):
        captured_cb["cb"] = cb

    monkeypatch.setattr(
        "custom_components.afvalwijzer.sensor.async_track_time_interval", _track
    )

    def _add_entities(_entities, _update):
        pass

    cfg = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }

    asyncio.run(_setup_sensors(hass, cfg, _add_entities, data))

    # Invoke the captured scheduler callback and ensure data.update was called
    assert captured_cb["cb"] is not None
    captured_cb["cb"](None)
    assert data._updates >= 1


def test_async_setup_entry_transient_error_raises(monkeypatch):
    """Transient backend error causes ConfigEntryNotReady to be raised."""
    hass = _make_hass()

    class _FakeAwData:
        def __init__(self, _h, _c):
            pass

        def update(self):
            return False, Exception("transient")

    monkeypatch.setattr(
        "custom_components.afvalwijzer.sensor.AfvalwijzerData", _FakeAwData
    )

    entry = SimpleNamespace()
    entry.data = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }
    entry.options = {}

    async def _add_entities(_entities, _update):
        pass

    with pytest.raises(Exception) as excinfo:
        asyncio.run(async_setup_entry(hass, entry, _add_entities))

    # Avoid importing Home Assistant exceptions; compare by class name
    assert excinfo.value.__class__.__name__ == "ConfigEntryNotReady"


def test_async_setup_entry_non_transient_failure_returns(monkeypatch):
    """Non-transient failure aborts setup without adding entities."""
    hass = _make_hass()

    class _FakeAwData:
        def __init__(self, _h, _c):
            pass

        def update(self):
            return False, None

    monkeypatch.setattr(
        "custom_components.afvalwijzer.sensor.AfvalwijzerData", _FakeAwData
    )

    entry = SimpleNamespace()
    entry.data = {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_SUFFIX: "",
        CONF_DEFAULT_LABEL: "geen",
    }
    entry.options = {}

    added = []

    def _add_entities(entities, _update):
        added.extend(entities)

    result = asyncio.run(async_setup_entry(hass, entry, _add_entities))
    # Should abort gracefully and not add entities
    assert result is None
    assert added == []
