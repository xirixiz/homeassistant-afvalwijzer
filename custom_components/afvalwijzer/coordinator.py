"""DataUpdateCoordinator for Afvalwijzer."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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

# Cache file in .storage
STORAGE_KEY = f"{DOMAIN}.cache"
STORAGE_VERSION = 1


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
            update_interval=timedelta(hours=4),
        )
        self.config = config
        storage_key = f"{DOMAIN}_{entry_id}.cache"
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, storage_key)
        self.waste_data_with_today: dict[str, Any] = {}
        self.waste_data_without_today: dict[str, Any] = {}
        self.waste_data_custom: dict[str, Any] = {}
        self.notification_data: list[Any] = []

    async def async_load_cache(self) -> bool:
        """Load data from the cache."""
        try:
            cached_data = await self._store.async_load()
            if cached_data and self._is_cache_for_current_config(cached_data):
                self._apply_data(cached_data["data"])
                self.data = cached_data["data"]
                _LOGGER.debug("Loaded Afvalwijzer data from cache")
                return True
        except Exception as err:
            _LOGGER.debug("Failed to load Afvalwijzer cache: %s", err)
        return False

    def _is_cache_for_current_config(self, cached_data: dict[str, Any]) -> bool:
        """Check if cache belongs to current postal code / house number."""
        cache_config = cached_data.get("config", {})
        return (
            cache_config.get(CONF_POSTAL_CODE) == self.config.get(CONF_POSTAL_CODE)
            and cache_config.get(CONF_HOUSE_NUMBER)
            == self.config.get(CONF_HOUSE_NUMBER)
            and cache_config.get(CONF_COLLECTOR) == self.config.get(CONF_COLLECTOR)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
            self._apply_data(data)

            # Save to cache
            cache_payload = {
                "config": {
                    CONF_POSTAL_CODE: self.config.get(CONF_POSTAL_CODE),
                    CONF_HOUSE_NUMBER: self.config.get(CONF_HOUSE_NUMBER),
                    CONF_COLLECTOR: self.config.get(CONF_COLLECTOR),
                },
                "data": data,
            }
            await self._store.async_save(cache_payload)

            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _apply_data(self, data: dict[str, Any]) -> None:
        """Apply fetched or cached data."""
        self.waste_data_with_today = data.get("waste_data_with_today", {})
        self.waste_data_without_today = data.get("waste_data_without_today", {})
        self.waste_data_custom = data.get("waste_data_custom", {})
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
                self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                self.config.get(CONF_EXCLUDE_LIST),
                self.config.get(CONF_DEFAULT_LABEL),
            )
        except Exception as err:
            raise UpdateFailed(f"Collector initialization failed: {err}") from err

        return {
            "waste_data_with_today": collector.waste_data_with_today,
            "waste_data_without_today": collector.waste_data_without_today,
            "waste_data_custom": collector.waste_data_custom,
            "notification_data": collector.notification_data,
        }
