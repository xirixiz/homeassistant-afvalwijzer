"""
Sensor component Afvalwijzer
Author: Bram van Dartel - xirixiz
"""

from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
from homeassistant.components.sensor import PLATFORM_SCHEMA
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .collector.main_collector import MainCollector
from .collector.secondary_collector import SecondaryCollector
from .const.const import (
    _LOGGER,
    CONF_COLLECTOR,
    CONF_SECONDARY_COLLECTOR,
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

# Define the platform schema for validation
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COLLECTOR, default="mijnafvalwijzer"): cv.string,
        vol.Optional(CONF_SECONDARY_COLLECTOR, default=""): cv.string,
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
    """Set up sensors using the platform schema."""
    if not discovery_info:
        _LOGGER.error(
            "No discovery information provided; sensors cannot be created.")
        return

    await _setup_sensors(hass, discovery_info, async_add_entities)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from a config entry."""
    await _setup_sensors(hass, entry.data, async_add_entities)


async def _setup_sensors(hass, config, async_add_entities):
    """Common setup logic for platform and config entry."""
    _LOGGER.debug(f"Setting up Afvalwijzer sensors for provider: {config.get(CONF_COLLECTOR)}.")

    # Initialize data handlers
    data = AfvalwijzerData(hass, config)
    secondary_data = SecondaryData(hass, config)

    # Perform an initial update at startup
    await hass.async_add_executor_job(data.update)

    if secondary_data:
        await hass.async_add_executor_job(secondary_data.update)

    # Schedule periodic updates every 4 hours
    update_interval = timedelta(hours=4)
    def schedule_update(_):
        """Safely schedule the update."""
        hass.loop.call_soon_threadsafe(hass.async_add_executor_job, data.update)
        if secondary_data.valid:
            hass.loop.call_soon_threadsafe(hass.async_add_executor_job, secondary_data.update)
    

    async_track_time_interval(hass, schedule_update, update_interval)

    # Fetch waste types
    try:
        waste_types_provider = set(data.waste_data_with_today.keys())
        waste_types_custom = set(data.waste_data_custom.keys())

        if secondary_data.valid:
            data.waste_data_with_today.update(secondary_data.waste_data_with_today)
            waste_types_provider.update(secondary_data.waste_data_with_today.keys())
    except Exception as err:
        _LOGGER.error(f"Failed to fetch waste types: {err}")
        return

    # Create entities
    entities = [
        ProviderSensor(hass, waste_type, data, secondary_data, config) for waste_type in waste_types_provider
    ] + [
        CustomSensor(hass, waste_type, data, config) for waste_type in waste_types_custom
    ]

    if not entities:
        _LOGGER.error(
            "No entities created; check configuration or collector output.")
        return

    _LOGGER.info(f"Adding {len(entities)} sensors for Afvalwijzer.")
    async_add_entities(entities, True)


class AfvalwijzerData:
    """Class to handle fetching and storing Afvalwijzer data."""

    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.waste_data_with_today = None
        self.waste_data_without_today = None
        self.waste_data_custom = None

    def update(self):
        """Fetch the latest waste data."""
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
            _LOGGER.error(f"Waste collector initialization failed: {err}")
            return

        try:
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom
            _LOGGER.debug("Waste data updated successfully.")
        except ValueError as err:
            _LOGGER.error(f"Failed to fetch waste data: {err}")
            self.waste_data_with_today = self.waste_data_without_today = self.waste_data_custom = self.config.get(CONF_DEFAULT_LABEL)

class SecondaryData:
    """Class to handle fetching and storing Secondary data."""

    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.valid = False
        self.waste_data_with_today = None
        self.waste_data_without_today = None
        self.waste_data_custom = None

    def update(self):
        """Fetch the latest waste data."""

        if not self.config.get(CONF_SECONDARY_COLLECTOR):
            self.valid = False
            return


        try:
            collector = SecondaryCollector(
                self.config.get(CONF_SECONDARY_COLLECTOR),
                self.config.get(CONF_POSTAL_CODE),
                self.config.get(CONF_STREET_NUMBER),
                self.config.get(CONF_SUFFIX),
                self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                self.config.get(CONF_DATE_ISOFORMAT),
                self.config.get(CONF_EXCLUDE_LIST),
                self.config.get(CONF_DEFAULT_LABEL),
            )
        except ValueError as err:
            _LOGGER.error(f"Secondary collector initialization failed: {err}")
            return

        try:
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom
            self.valid = True
            _LOGGER.debug("Secondary waste data updated successfully.")
        except ValueError as err:
            _LOGGER.error(f"Failed to fetch secondary waste data: {err}")
            self.waste_data_with_today = self.waste_data_without_today = self.waste_data_custom = self.config.get(CONF_DEFAULT_LABEL)