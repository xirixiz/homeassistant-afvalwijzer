"""Tests for the Afvalwijzer coordinator cache handling."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
)
from custom_components.afvalwijzer.coordinator import (
    RETRY_INTERVALS,
    UPDATE_INTERVAL,
    AfvalwijzerDataUpdateCoordinator,
    async_remove_cache,
)
from homeassistant.helpers.update_coordinator import UpdateFailed
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
    coordinator._failed_refreshes = 0
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
    assert CONF_SUFFIX in saved["config"]
    assert CONF_STREET_NAME in saved["config"]
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


def _make_real_coordinator(config):
    """Build a coordinator by actually running AfvalwijzerDataUpdateCoordinator.__init__.

    The HA base class's __init__ requires a fully set up hass (frame helper
    etc.) that a bare MagicMock can't satisfy, so it's stubbed out here -
    everything specific to our own __init__ body (config, supports_notifications,
    ...) still runs for real.
    """
    with patch(
        "custom_components.afvalwijzer.coordinator.DataUpdateCoordinator.__init__",
        return_value=None,
    ):
        return AfvalwijzerDataUpdateCoordinator(MagicMock(), config, "entry")


def test_init_sets_supports_notifications_for_capable_provider():
    """A provider that supports notifications is detected at construction time.

    This must be derivable from config alone (no fetch required), since
    sensor.py decides whether to create the notifications entity before any
    data has necessarily been fetched.
    """
    coordinator = _make_real_coordinator(dict(_CONFIG))
    assert coordinator.supports_notifications is True


def test_init_sets_supports_notifications_false_for_incapable_provider():
    """A provider outside the known notification-capable sets is detected too."""
    config = {**_CONFIG, CONF_COLLECTOR: "rova"}
    coordinator = _make_real_coordinator(config)
    assert coordinator.supports_notifications is False


async def test_update_keeps_previous_schedule_when_provider_returns_nothing():
    """An empty result must not replace a schedule we already have."""
    coordinator = _make_coordinator()
    coordinator.data = dict(_DATA)
    coordinator._apply_data(coordinator.data)

    async def _exec(fn, *args):
        return fn(*args)

    coordinator.hass = SimpleNamespace(async_add_executor_job=_exec)
    coordinator._fetch_data = lambda: {
        "waste_data_with_today": {},
        "waste_data_without_today": {},
        "waste_data_custom": {},
        "waste_data_raw": [],
        "notification_data": [],
    }
    save_mock = AsyncMock()
    coordinator._store = SimpleNamespace(async_save=save_mock)

    result = await coordinator._async_update_data()

    assert result == _DATA
    assert coordinator.waste_data_raw == _DATA["waste_data_raw"]
    assert coordinator.waste_data_with_today == _DATA["waste_data_with_today"]
    save_mock.assert_not_awaited()


async def test_update_accepts_empty_result_without_previous_schedule():
    """With nothing to keep, an empty result is applied as before."""
    coordinator = _make_coordinator()

    async def _exec(fn, *args):
        return fn(*args)

    coordinator.hass = SimpleNamespace(async_add_executor_job=_exec)
    empty = {
        "waste_data_with_today": {},
        "waste_data_without_today": {},
        "waste_data_custom": {},
        "waste_data_raw": [],
        "notification_data": [],
    }
    coordinator._fetch_data = lambda: dict(empty)
    save_mock = AsyncMock()
    coordinator._store = SimpleNamespace(async_save=save_mock)

    assert await coordinator._async_update_data() == empty
    save_mock.assert_awaited_once()


# --- cache scope: the full address -------------------------------------------------


def test_cache_for_another_suffix_is_not_used():
    """Reconfiguring 5 to 5A must not show the schedule of 5 while refreshing."""
    cached = _cache_payload(config=dict(_CONFIG, **{CONF_SUFFIX: ""}))
    coordinator = _make_coordinator(dict(_CONFIG, **{CONF_SUFFIX: "A"}))

    assert coordinator._is_cache_for_current_config(cached) is False


def test_cache_for_another_street_is_not_used():
    """Providers that need the street name must not share a schedule across streets."""
    cached = _cache_payload(config=dict(_CONFIG, **{CONF_STREET_NAME: "Dorpsstraat"}))
    coordinator = _make_coordinator(dict(_CONFIG, **{CONF_STREET_NAME: "Kerkstraat"}))

    assert coordinator._is_cache_for_current_config(cached) is False


def test_cache_scope_ignores_case_whitespace_and_empty_values():
    """None, "" and a missing key are the same, and text is compared normalized."""
    cached = _cache_payload(
        config=dict(_CONFIG, **{CONF_SUFFIX: "a ", CONF_STREET_NAME: None})
    )
    coordinator = _make_coordinator(
        dict(_CONFIG, **{CONF_SUFFIX: "A", CONF_STREET_NAME: ""})
    )

    assert coordinator._is_cache_for_current_config(cached) is True


def test_cache_from_before_the_suffix_was_stored_still_matches_without_one():
    """Existing caches don't hold a suffix or street key, and are still used."""
    legacy = _cache_payload()
    assert CONF_SUFFIX not in legacy["config"]

    assert _make_coordinator()._is_cache_for_current_config(legacy) is True
    with_suffix = _make_coordinator(dict(_CONFIG, **{CONF_SUFFIX: "A"}))
    assert with_suffix._is_cache_for_current_config(legacy) is False


# --- retry after a failed refresh --------------------------------------------------


def test_retry_intervals_back_off_and_a_success_resets_them():
    """5, 15 and 30 minutes, then hourly while it keeps failing; a success resets."""
    coordinator = _make_coordinator()
    seen = []

    for _ in range(6):
        coordinator._record_refresh_result(success=False)
        seen.append(coordinator.update_interval)
    assert seen == [
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=30),
        timedelta(hours=1),
        timedelta(hours=1),
        timedelta(hours=1),
    ]

    coordinator._record_refresh_result(success=True)
    assert coordinator.update_interval == UPDATE_INTERVAL

    coordinator._record_refresh_result(success=False)
    assert coordinator.update_interval == timedelta(minutes=5)  # starts over


def test_retry_is_never_later_than_the_regular_interval():
    """Every backoff step is shorter than the regular interval."""
    assert all(interval <= UPDATE_INTERVAL for interval in RETRY_INTERVALS)
    assert RETRY_INTERVALS[0] < UPDATE_INTERVAL


async def test_failed_update_shortens_the_interval_and_raises():
    """A failure is reported to Home Assistant, which then retries after the backoff."""
    coordinator = _make_coordinator()

    async def _exec(fn, *args):
        return fn(*args)

    def _fail():
        raise RuntimeError("provider down")

    coordinator.hass = SimpleNamespace(async_add_executor_job=_exec)
    coordinator._fetch_data = _fail
    coordinator._store = SimpleNamespace(async_save=AsyncMock())

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(minutes=5)


async def test_empty_provider_answer_keeps_the_regular_interval():
    """Keeping the previous schedule is not a failure, so there is no quick retry."""
    coordinator = _make_coordinator()
    coordinator.data = dict(_DATA)
    coordinator._apply_data(coordinator.data)
    coordinator._failed_refreshes = 2

    async def _exec(fn, *args):
        return fn(*args)

    coordinator.hass = SimpleNamespace(async_add_executor_job=_exec)
    coordinator._fetch_data = lambda: {"waste_data_raw": []}
    coordinator._store = SimpleNamespace(async_save=AsyncMock())

    await coordinator._async_update_data()

    assert coordinator.update_interval == UPDATE_INTERVAL
    assert coordinator._failed_refreshes == 0


async def test_scheduler_retries_sooner_and_returns_to_the_regular_interval(
    hass, freezer
):
    """With the real scheduler: retry after 5 and 15 minutes, then every 4 hours."""
    coordinator = AfvalwijzerDataUpdateCoordinator(hass, dict(_CONFIG), "entry")
    coordinator._store = SimpleNamespace(async_save=AsyncMock())
    fetch = MagicMock(
        side_effect=[
            RuntimeError("down"),
            RuntimeError("down"),
            dict(_DATA),
            dict(_DATA),
        ]
    )
    coordinator._fetch_data = fetch
    # Refreshes are only scheduled while something listens, like the entities do
    unsubscribe = coordinator.async_add_listener(lambda: None)

    async def advance(delta):
        freezer.tick(delta)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    await coordinator.async_refresh()
    assert fetch.call_count == 1
    assert coordinator.last_update_success is False

    await advance(timedelta(minutes=4, seconds=50))
    assert fetch.call_count == 1  # not yet

    await advance(timedelta(seconds=15))
    assert fetch.call_count == 2  # after 5 minutes: fails again
    assert coordinator.last_update_success is False

    await advance(timedelta(minutes=14))
    assert fetch.call_count == 2  # backed off to 15 minutes

    await advance(timedelta(minutes=2))
    assert fetch.call_count == 3  # succeeds
    assert coordinator.last_update_success is True
    assert coordinator.update_interval == UPDATE_INTERVAL

    await advance(timedelta(hours=3, minutes=50))
    assert fetch.call_count == 3  # now the regular interval again

    await advance(timedelta(minutes=15))
    assert fetch.call_count == 4

    unsubscribe()
    await coordinator.async_shutdown()
