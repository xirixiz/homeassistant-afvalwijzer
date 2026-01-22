"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .collector.main_collector import MainCollector
from .const.const import (
    _LOGGER,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    SCAN_INTERVAL,
)
from .sensor_custom import CustomSensor
from .sensor_provider import ProviderSensor

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COLLECTOR, default="mijnafvalwijzer"): cv.string,
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_STREET_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
        vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities,
    discovery_info=None,
) -> None:
    """Set up sensors via YAML or discovery (legacy)."""
    cfg = discovery_info or config
    if not cfg:
        _LOGGER.error("Missing configuration; sensors cannot be created.")
        return

    await _setup_sensors(hass, cfg, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensors from a config entry (config flow)."""
    config: dict[str, Any] = {**entry.data, **entry.options}

    data = AfvalwijzerData(hass, config)

    ok, transient_error = await hass.async_add_executor_job(data.update)
    if not ok and transient_error is not None:
        _LOGGER.warning("Afvalwijzer backend not ready yet; will retry setup.")
        raise ConfigEntryNotReady from transient_error
    if not ok:
        _LOGGER.error("Afvalwijzer initial update failed; aborting setup for this entry.")
        return

    await _setup_sensors(hass, config, async_add_entities, data)


async def _setup_sensors(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities,
    data: AfvalwijzerData | None = None,
) -> None:
    """General setup logic for platform and config entry."""
    _LOGGER.debug(
        "Setting up Afvalwijzer sensors for provider: %s.",
        config.get(CONF_COLLECTOR),
    )

    if data is None:
        data = AfvalwijzerData(hass, config)
        ok, transient_error = await hass.async_add_executor_job(data.update)
        if not ok and transient_error is not None:
            _LOGGER.warning(
                "Afvalwijzer backend not ready during platform setup; skipping.",
            )
            return
        if not ok:
            _LOGGER.error("Afvalwijzer failed to fetch initial data; skipping setup.")
            return

    update_interval = SCAN_INTERVAL or timedelta(hours=4)

    @callback
    def _schedule_update(_now) -> None:
        hass.async_add_executor_job(data.update)

    async_track_time_interval(hass, _schedule_update, update_interval)

    waste_data_with_today = data.waste_data_with_today or {}
    waste_data_custom = data.waste_data_custom or {}

    entities: list[Any] = [
        ProviderSensor(hass, wtype, data, config) for wtype in waste_data_with_today
    ]
    entities.extend(CustomSensor(hass, wtype, data, config) for wtype in waste_data_custom)

    if data.notification_data is not None:
        entities.append(ProviderSensor(hass, "notifications", data, config))
        _LOGGER.debug("Added notification sensor for provider")

    if not entities:
        _LOGGER.error("No entities created; check configuration or collector output.")
        return

    _LOGGER.info("Adding %d sensors for Afvalwijzer.", len(entities))
    async_add_entities(entities, True)


class AfvalwijzerData:
    """Handles fetching and storing Afvalwijzer data."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the Afvalwijzer base sensor."""
        self.hass = hass
        self.config = config
        self.waste_data_with_today: dict[str, Any] | None = None
        self.waste_data_without_today: dict[str, Any] | None = None
        self.waste_data_custom: dict[str, Any] | None = None
        self.notification_data: list[Any] | None = None

    def update(self) -> tuple[bool, Exception | None]:
        """Fetch the latest waste data."""
        try:
            collector = MainCollector(
                self.config.get(CONF_COLLECTOR),
                self.config.get(CONF_POSTAL_CODE),
                self.config.get(CONF_STREET_NUMBER),
                self.config.get(CONF_SUFFIX),
                self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                self.config.get(CONF_EXCLUDE_LIST),
                self.config.get(CONF_DEFAULT_LABEL),
            )
        except ValueError as err:
            _LOGGER.error("Collector initialization failed: %s", err)
            return False, None
        except Exception as err:
            _LOGGER.warning("Collector init unexpected error: %s", err)
            return False, err

        try:
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom
            self.notification_data = collector.notification_data
            _LOGGER.debug("Waste data updated successfully.")
            return True, None
        except TimeoutError as err:
            _LOGGER.warning("Timeout fetching waste data: %s", err)
            return False, err
        except ConnectionError as err:
            _LOGGER.warning("Connection error fetching waste data: %s", err)
            return False, err
        except ValueError as err:
            _LOGGER.error("Failed to fetch waste data: %s", err)
            self.waste_data_with_today = {}
            self.waste_data_without_today = {}
            self.waste_data_custom = {}
            self.notification_data = []
            return False, None
        except Exception as err:
            _LOGGER.warning("Unexpected error fetching waste data: %s", err)
            return False, err
