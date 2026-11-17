"""DataUpdateCoordinator for Afvalwijzer."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .collector.main_collector import MainCollector
from .const.const import (
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

# Cached data older than this is ignored at startup
MAX_CACHE_AGE = timedelta(days=7)

# The regular interval between refreshes.
UPDATE_INTERVAL = timedelta(hours=4)

# After a failed refresh, retry sooner than the regular interval and back off while
# the provider stays unreachable (a reboot before the network is up, a short
# outage). A success returns to the regular interval.
RETRY_INTERVALS = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
    timedelta(hours=1),
)


def _build_cache_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the per-entry cache store in .storage."""
    return Store[dict[str, Any]](hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}.cache")


async def async_remove_cache(hass: HomeAssistant, entry_id: str) -> None:
    """Remove the cache file belonging to a removed config entry."""
    await _build_cache_store(hass, entry_id).async_remove()


class AfvalwijzerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Afvalwijzer data."""

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], entry_id: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.config = config
        self._failed_refreshes = 0
        self._store = _build_cache_store(hass, entry_id)
        self.waste_data_with_today: dict[str, Any] = {}
        self.waste_data_without_today: dict[str, Any] = {}
        self.waste_data_custom: dict[str, Any] = {}
        self.waste_data_raw: list[dict[str, Any]] = []
        self.notification_data: list[Any] = []
        self.supports_notifications = MainCollector.provider_supports_notifications(
            config.get(CONF_COLLECTOR)
        )

    async def async_load_cache(self) -> bool:
        """Load data from the cache."""
        try:
            cached_data = await self._store.async_load()
            if (
                cached_data
                and self._is_cache_for_current_config(cached_data)
                and not self._is_cache_stale(cached_data)
            ):
                self._apply_data(cached_data["data"])
                self.data = cached_data["data"]
                _LOGGER.debug("Loaded Afvalwijzer data from cache")
                return True
        except Exception as err:
            _LOGGER.debug("Failed to load Afvalwijzer cache: %s", err)
        return False

    @staticmethod
    def _is_cache_stale(cached_data: dict[str, Any]) -> bool:
        """Return True if the cache is too old to be trusted at startup."""
        fetched_at = dt_util.parse_datetime(str(cached_data.get("fetched_at", "")))
        if fetched_at is None:
            return True
        return dt_util.utcnow() - fetched_at > MAX_CACHE_AGE

    @staticmethod
    def _cache_scope(config: dict[str, Any]) -> tuple[str, ...]:
        """Return what identifies the address and collector a schedule belongs to.

        A missing value counts as empty, so caches written before the suffix and
        street name were stored still match an address without them.
        """
        return tuple(
            str(config.get(key) or "").strip().casefold()
            for key in (
                CONF_COLLECTOR,
                CONF_POSTAL_CODE,
                CONF_HOUSE_NUMBER,
                CONF_SUFFIX,
                CONF_STREET_NAME,
            )
        )

    def _is_cache_for_current_config(self, cached_data: dict[str, Any]) -> bool:
        """Check if cache belongs to the current collector and full address."""
        return self._cache_scope(cached_data.get("config") or {}) == self._cache_scope(
            self.config
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)

            # Providers answer "no data" / "address not found" with an empty schedule instead
            # of an error. Don't let that replace a schedule we already have.
            if not data.get("waste_data_raw") and self._has_schedule():
                _LOGGER.warning(
                    "Provider returned no pickup data, keeping the previous schedule"
                )
                self._record_refresh_result(success=True)
                return self.data

            self._apply_data(data)

            # Save to cache
            cache_payload = {
                "config": {
                    CONF_POSTAL_CODE: self.config.get(CONF_POSTAL_CODE),
                    CONF_HOUSE_NUMBER: self.config.get(CONF_HOUSE_NUMBER),
                    CONF_COLLECTOR: self.config.get(CONF_COLLECTOR),
                    CONF_SUFFIX: self.config.get(CONF_SUFFIX),
                    CONF_STREET_NAME: self.config.get(CONF_STREET_NAME),
                },
                "fetched_at": dt_util.utcnow().isoformat(),
                "data": data,
            }
            await self._store.async_save(cache_payload)

            self._record_refresh_result(success=True)
            return data
        except Exception as err:
            self._record_refresh_result(success=False)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _record_refresh_result(self, *, success: bool) -> None:
        """Set the interval until the next refresh: regular, or a backoff after a failure.

        Home Assistant schedules the next refresh right after this one, using the
        current update_interval.
        """
        if success:
            self._failed_refreshes = 0
            self.update_interval = UPDATE_INTERVAL
            return
        retry = RETRY_INTERVALS[min(self._failed_refreshes, len(RETRY_INTERVALS) - 1)]
        self._failed_refreshes += 1
        self.update_interval = min(retry, UPDATE_INTERVAL)

    def _has_schedule(self) -> bool:
        """Return True if a non-empty schedule was fetched or loaded from the cache."""
        return bool(self.data and self.data.get("waste_data_raw"))

    def _apply_data(self, data: dict[str, Any]) -> None:
        """Apply fetched or cached data."""
        self.waste_data_with_today = data.get("waste_data_with_today", {})
        self.waste_data_without_today = data.get("waste_data_without_today", {})
        self.waste_data_custom = data.get("waste_data_custom", {})
        self.waste_data_raw = data.get("waste_data_raw", [])
        self.notification_data = data.get("notification_data", [])

    def _fetch_data(self) -> dict[str, Any]:
        """Fetch data synchronously."""
        try:
            collector = MainCollector(
                self.config.get(CONF_COLLECTOR),
                self.config.get(CONF_POSTAL_CODE),
                self.config.get(CONF_HOUSE_NUMBER),
                self.config.get(CONF_SUFFIX),
                self.config.get(CONF_STREET_NAME),
                exclude_pickup_today=self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                exclude_list=self.config.get(CONF_EXCLUDE_LIST),
                default_label=self.config.get(CONF_DEFAULT_LABEL),
            )
        except Exception as err:
            raise UpdateFailed(f"Collector initialization failed: {err}") from err

        return {
            "waste_data_with_today": collector.waste_data_with_today,
            "waste_data_without_today": collector.waste_data_without_today,
            "waste_data_custom": collector.waste_data_custom,
            "waste_data_raw": collector.waste_data_raw,
            "notification_data": collector.notification_data,
        }
