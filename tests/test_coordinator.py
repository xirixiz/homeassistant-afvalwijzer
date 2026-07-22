"""Tests for the Afvalwijzer coordinator cache handling."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
)
from custom_components.afvalwijzer.coordinator import (
    AfvalwijzerDataUpdateCoordinator,
    async_remove_cache,
)
from homeassistant.util import dt as dt_util

_CONFIG = {
    CONF_COLLECTOR: "mijnafvalwijzer",
    CONF_POSTAL_CODE: "1234AB",
    CONF_HOUSE_NUMBER: "1",
}

_DATA = {
    "waste_data_with_today": {"restafval": "2026-07-23"},
    "waste_data_without_today": {"restafval": "2026-07-23"},
    "waste_data_custom": {"next_date": "2026-07-23"},
    "waste_data_raw": [
        {"type": "restafval", "date": "2026-07-23"},
        {"type": "restafval", "date": "2026-08-06"},
    ],
    "notification_data": ["note"],
}


def _make_coordinator(config=None):
    """Build a coordinator without running DataUpdateCoordinator.__init__."""
    coordinator = AfvalwijzerDataUpdateCoordinator.__new__(
        AfvalwijzerDataUpdateCoordinator
    )
    coordinator.config = dict(config or _CONFIG)
    coordinator.data = None
    coordinator.waste_data_with_today = {}
    coordinator.waste_data_without_today = {}
    coordinator.waste_data_custom = {}
    coordinator.waste_data_raw = []
    coordinator.notification_data = []
    return coordinator


def _cache_payload(*, fetched_at=None, config=None, data=None):
    payload = {
        "config": dict(config or _CONFIG),
        "data": dict(data or _DATA),
    }
    if fetched_at is not None:
        payload["fetched_at"] = fetched_at
    return payload


def test_cache_stale_when_fetched_at_missing():
    """A cache without a fetch timestamp is not trusted."""
    assert AfvalwijzerDataUpdateCoordinator._is_cache_stale(_cache_payload()) is True


def test_cache_stale_when_fetched_at_invalid():
    """A cache with an unparseable timestamp is not trusted."""
    payload = _cache_payload(fetched_at="not-a-date")
    assert AfvalwijzerDataUpdateCoordinator._is_cache_stale(payload) is True


def test_cache_fresh_when_recent():
    """A recently written cache is accepted."""
    payload = _cache_payload(fetched_at=dt_util.utcnow().isoformat())
    assert AfvalwijzerDataUpdateCoordinator._is_cache_stale(payload) is False


def test_cache_stale_when_too_old():
    """A cache older than the maximum age is rejected."""
    old = (dt_util.utcnow() - timedelta(days=8)).isoformat()
    payload = _cache_payload(fetched_at=old)
    assert AfvalwijzerDataUpdateCoordinator._is_cache_stale(payload) is True


def test_cache_config_match_and_mismatch():
    """Cache is only valid for the same collector and address."""
    coordinator = _make_coordinator()

    assert coordinator._is_cache_for_current_config(_cache_payload()) is True

    other = dict(_CONFIG, **{CONF_POSTAL_CODE: "9999ZZ"})
    assert (
        coordinator._is_cache_for_current_config(_cache_payload(config=other)) is False
    )


async def test_async_load_cache_applies_fresh_cache():
    """A fresh, matching cache is loaded and applied."""
    coordinator = _make_coordinator()
    payload = _cache_payload(fetched_at=dt_util.utcnow().isoformat())
    coordinator._store = SimpleNamespace(async_load=AsyncMock(return_value=payload))

    assert await coordinator.async_load_cache() is True
    assert coordinator.data == _DATA
    assert coordinator.waste_data_with_today == _DATA["waste_data_with_today"]
    assert coordinator.waste_data_raw == _DATA["waste_data_raw"]
    assert coordinator.notification_data == ["note"]


async def test_async_load_cache_rejects_stale_cache():
    """A stale cache is ignored so a fresh fetch happens instead."""
    coordinator = _make_coordinator()
    old = (dt_util.utcnow() - timedelta(days=30)).isoformat()
    payload = _cache_payload(fetched_at=old)
    coordinator._store = SimpleNamespace(async_load=AsyncMock(return_value=payload))

    assert await coordinator.async_load_cache() is False
    assert coordinator.data is None


async def test_async_load_cache_rejects_other_address():
    """A cache written for a different address is ignored."""
    coordinator = _make_coordinator()
    other = dict(_CONFIG, **{CONF_HOUSE_NUMBER: "99"})
    payload = _cache_payload(fetched_at=dt_util.utcnow().isoformat(), config=other)
    coordinator._store = SimpleNamespace(async_load=AsyncMock(return_value=payload))

    assert await coordinator.async_load_cache() is False


async def test_async_load_cache_survives_store_errors():
    """Storage errors fall back to a normal first refresh."""
    coordinator = _make_coordinator()
    coordinator._store = SimpleNamespace(
        async_load=AsyncMock(side_effect=OSError("disk error"))
    )

    assert await coordinator.async_load_cache() is False


async def test_update_data_saves_cache_with_fetched_at():
    """A successful update writes the cache including a fetch timestamp."""
    coordinator = _make_coordinator()

    async def _exec(fn, *args):
        return fn(*args)

    coordinator.hass = SimpleNamespace(async_add_executor_job=_exec)
    coordinator._fetch_data = lambda: dict(_DATA)
    save_mock = AsyncMock()
    coordinator._store = SimpleNamespace(async_save=save_mock)

    result = await coordinator._async_update_data()

    assert result == _DATA
    save_mock.assert_awaited_once()
    saved = save_mock.await_args.args[0]
    assert saved["data"] == _DATA
    assert saved["config"][CONF_POSTAL_CODE] == "1234AB"
    assert dt_util.parse_datetime(saved["fetched_at"]) is not None
    # The freshly saved payload must pass its own staleness check
    assert AfvalwijzerDataUpdateCoordinator._is_cache_stale(saved) is False


async def test_async_remove_cache_removes_store():
    """Removing the cache removes the per-entry store file."""
    store = MagicMock()
    store.async_remove = AsyncMock()

    with patch(
        "custom_components.afvalwijzer.coordinator._build_cache_store",
        return_value=store,
    ) as build_mock:
        await async_remove_cache(MagicMock(), "entry_123")

    build_mock.assert_called_once()
    assert build_mock.call_args.args[1] == "entry_123"
    store.async_remove.assert_awaited_once()
