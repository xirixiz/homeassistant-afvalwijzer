"""
Sensor component Afvalwijzer
Author: Bram van Dartel - xirixiz
"""

from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .collector.main_collector import MainCollector
from .const.const import (
    _LOGGER,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_DATE_ISOFORMAT,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    CONF_USERNAME,
    CONF_PASSWORD,
    SCAN_INTERVAL,
)
from .sensor_custom import CustomSensor
from .sensor_provider import ProviderSensor

# Platform schema (YAML) – keep if you still support YAML
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COLLECTOR, default="mijnafvalwijzer"): cv.string,
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_STREET_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_USERNAME, default=""): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
        vol.Optional(CONF_DATE_ISOFORMAT, default=False): cv.boolean,
        vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
        vol.Optional(CONF_ID, default=""): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensors via YAML or discovery (legacy)."""
    cfg = discovery_info or config
    if not cfg:
        _LOGGER.error("Missing configuration; sensors cannot be created.")
        return

    await _setup_sensors(hass, cfg, async_add_entities)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from a config entry (config flow)."""
    data = AfvalwijzerData(hass, entry.data)

    # Perform an initial update; if upstream not ready, ask HA to retry later
    ok, transient_error = await hass.async_add_executor_job(data.update)
    if not ok and transient_error:
        _LOGGER.warning("Afvalwijzer backend not ready yet; will retry setup.")
        raise ConfigEntryNotReady from transient_error
    if not ok:
        # Non-recoverable error already logged in update(); abort setup for this entry
        _LOGGER.error("Afvalwijzer initial update failed; aborting setup for this entry.")
        return

    await _setup_sensors(hass, entry.data, async_add_entities, data)


async def _setup_sensors(hass, config, async_add_entities, data: "AfvalwijzerData" | None = None):
    """Common setup logic for platform and config entry."""
    _LOGGER.debug(
        "Setting up Afvalwijzer sensors for provider: %s.",
        config.get(CONF_COLLECTOR),
    )

    # Initialize data handler if not provided
    if data is None:
        data = AfvalwijzerData(hass, config)
        ok, transient_error = await hass.async_add_executor_job(data.update)
        if not ok and transient_error:
            _LOGGER.warning("Afvalwijzer backend not ready during platform setup; skipping.")
            return
        if not ok:
            _LOGGER.error("Afvalwijzer failed to fetch initial data; skipping setup.")
            return

    # Schedule periodic updates every 4 hours (or SCAN_INTERVAL if you prefer)
    update_interval = timedelta(hours=4) if SCAN_INTERVAL is None else SCAN_INTERVAL

    def schedule_update(_):
        """Safely schedule the update on the executor thread."""
        hass.loop.call_soon_threadsafe(hass.async_add_executor_job, data.update)

    async_track_time_interval(hass, schedule_update, update_interval)

    # Fetch waste types to build entities
    try:
        waste_types_provider = data.waste_data_with_today.keys()
        waste_types_custom = data.waste_data_custom.keys()
    except Exception as err:
        _LOGGER.error("Failed to fetch waste types: %s", err)
        return

    entities = [
        ProviderSensor(hass, waste_type, data, config) for waste_type in waste_types_provider
    ] + [
        CustomSensor(hass, waste_type, data, config) for waste_type in waste_types_custom
    ]

    if not entities:
        _LOGGER.error("No entities created; check configuration or collector output.")
        return

    _LOGGER.info("Adding %d sensors for Afvalwijzer.", len(entities))
    async_add_entities(entities, True)


class AfvalwijzerData:
    """Handles fetching and storing Afvalwijzer data."""

    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.waste_data_with_today = None
        self.waste_data_without_today = None
        self.waste_data_custom = None

    def update(self):
        """
        Fetch the latest waste data.

        Returns:
            (ok: bool, transient_error: Exception | None)

        Contract:
        - Return (True, None) on success.
        - For *temporary* problems (network, timeouts, 5xx), return (False, exc).
        - For *permanent* config/data errors, log and return (False, None).
        """
        try:
            collector = MainCollector(
                self.config.get(CONF_COLLECTOR),
                self.config.get(CONF_POSTAL_CODE),
                self.config.get(CONF_STREET_NUMBER),
                self.config.get(CONF_SUFFIX),
                self.config.get(CONF_USERNAME),
                self.config.get(CONF_PASSWORD),
                self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                self.config.get(CONF_DATE_ISOFORMAT),
                self.config.get(CONF_EXCLUDE_LIST),
                self.config.get(CONF_DEFAULT_LABEL),
            )
        except ValueError as err:
            # Likely a configuration / validation error -> non-recoverable here
            _LOGGER.error("Collector initialization failed: %s", err)
            return False, None
        except Exception as err:
            # Unexpected but possibly transient
            _LOGGER.warning("Collector init hit an unexpected error: %s", err)
            return False, err

        try:
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom
            _LOGGER.debug("Waste data updated successfully.")
            return True, None
        except TimeoutError as err:
            _LOGGER.warning("Timeout fetching waste data: %s", err)
            return False, err
        except ConnectionError as err:  # noqa: F821 (if not imported; safe in runtime)
            _LOGGER.warning("Connection error fetching waste data: %s", err)
            return False, err
        except ValueError as err:
            # Bad/invalid response that won't fix itself without config change
            _LOGGER.error("Failed to fetch waste data: %s", err)
            self.waste_data_with_today = (
                self.waste_data_without_today
            ) = self.waste_data_custom = self.config.get(CONF_DEFAULT_LABEL)
            return False, None
        except Exception as err:
            # Unknown; assume transient so HA can retry setup if needed
            _LOGGER.warning("Unexpected error fetching waste data: %s", err)
            return False, err
