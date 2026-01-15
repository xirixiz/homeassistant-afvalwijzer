"""Afvalwijzer integration."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .collector.main_collector import MainCollector
from .const.const import (
    _LOGGER,
    CONF_COLLECTOR,
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    SCAN_INTERVAL,
)
from .sensor_custom import CustomSensor
from .sensor_provider import ProviderSensor

# YAML support (optional / legacy)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COLLECTOR, default="mijnafvalwijzer"): cv.string,
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_STREET_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
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

    # Initial fetch; if upstream not ready, ask HA to retry
    ok, transient_error = await hass.async_add_executor_job(data.update)
    if not ok and transient_error:
        _LOGGER.warning("Afvalwijzer backend not ready yet; will retry setup.")
        raise ConfigEntryNotReady from transient_error
    if not ok:
        _LOGGER.error(
            "Afvalwijzer initial update failed; aborting setup for this entry."
        )
        return

    await _setup_sensors(hass, entry.data, async_add_entities, data)


async def _setup_sensors(hass, config, async_add_entities, data=None):
    """General setup logic for platform and config entry."""
    _LOGGER.debug(
        "Setting up Afvalwijzer sensors for provider: %s.",
        config.get(CONF_COLLECTOR),
    )

    if data is None:
        data = AfvalwijzerData(hass, config)
        ok, transient_error = await hass.async_add_executor_job(data.update)
        if not ok and transient_error:
            _LOGGER.warning(
                "Afvalwijzer backend not ready during platform setup; skipping."
            )
            return
        if not ok:
            _LOGGER.error("Afvalwijzer failed to fetch initial data; skipping setup.")
            return

    # Update cadence
    update_interval = SCAN_INTERVAL if SCAN_INTERVAL else timedelta(hours=4)

    def schedule_update(_):
        """Schedule the update on the executor thread."""
        hass.loop.call_soon_threadsafe(hass.async_add_executor_job, data.update)

    async_track_time_interval(hass, schedule_update, update_interval)

    # Build entities
    try:
        waste_types_provider = data.waste_data_with_today.keys()
        waste_types_custom = data.waste_data_custom.keys()
    except Exception as err:
        _LOGGER.error("Failed to fetch waste types: %s", err)
        return

    entities = [
        ProviderSensor(hass, wtype, data, config) for wtype in waste_types_provider
    ] + [CustomSensor(hass, wtype, data, config) for wtype in waste_types_custom]

    # Add notification sensor if provider supports it
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

    def __init__(self, hass, config):
        """Initialize Afvalwijzer data handler."""
        self.hass = hass
        self.config = config
        self.waste_data_with_today = None
        self.waste_data_without_today = None
        self.waste_data_custom = None
        self.notification_data = None

    def update(self):
        """Fetch the latest waste data.

        Returns:
            (ok: bool, transient_error: Exception | None)

        """
        try:
            collector = MainCollector(
                self.config.get(CONF_COLLECTOR),
                self.config.get(CONF_POSTAL_CODE),
                self.config.get(CONF_STREET_NUMBER),
                self.config.get(CONF_SUFFIX),
                self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                self.config.get(CONF_DATE_ISOFORMAT),
                self.config.get(CONF_EXCLUDE_LIST),
                self.config.get(CONF_DEFAULT_LABEL),
            )
        except ValueError as err:
            _LOGGER.error("Collector initialization failed: %s", err)
            return False, None
        except Exception as err:
            # Unexpected; may be transient
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
            self.waste_data_with_today = self.waste_data_without_today = (
                self.waste_data_custom
            ) = self.config.get(CONF_DEFAULT_LABEL)
            return False, None
        except Exception as err:
            _LOGGER.warning("Unexpected error fetching waste data: %s", err)
            return False, err
