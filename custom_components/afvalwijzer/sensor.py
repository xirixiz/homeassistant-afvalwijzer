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

# Define the platform schema for validation
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
    provider = config.get(CONF_COLLECTOR)
    postal_code = config.get(CONF_POSTAL_CODE)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX, "")
    username = config.get(CONF_USERNAME, "")
    password = config.get(CONF_PASSWORD, "")
    exclude_pickup_today = config.get(CONF_EXCLUDE_PICKUP_TODAY, True)
    date_isoformat = config.get(CONF_DATE_ISOFORMAT, False)
    exclude_list = config.get(CONF_EXCLUDE_LIST, "")
    default_label = config.get(CONF_DEFAULT_LABEL, "geen")

    _LOGGER.debug(f"Setting up Afvalwijzer sensors for provider: {provider}.")

    # Initialize data handler
    data = AfvalwijzerData(hass, config)

    # Perform an initial update at startup
    await hass.async_add_executor_job(data.update)

    # Schedule periodic updates every 4 hours
    update_interval = timedelta(hours=4)
    def schedule_update(_):
        """Safely schedule the update."""
        hass.loop.call_soon_threadsafe(hass.async_add_executor_job, data.update)
    
    async_track_time_interval(hass, schedule_update, update_interval)


    # Fetch waste types
    try:
        waste_types_provider = data.waste_data_with_today.keys()
        waste_types_custom = data.waste_data_custom.keys()
    except Exception as err:
        _LOGGER.error(f"Failed to fetch waste types: {err}")
        return

    # Create entities
    entities = [
        ProviderSensor(hass, waste_type, data, config) for waste_type in waste_types_provider
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
        provider = self.config.get(CONF_COLLECTOR)
        postal_code = self.config.get(CONF_POSTAL_CODE)
        street_number = self.config.get(CONF_STREET_NUMBER)
        suffix = self.config.get(CONF_SUFFIX)
        username = self.config.get(CONF_USERNAME)
        password = self.config.get(CONF_PASSWORD)
        exclude_pickup_today = self.config.get(CONF_EXCLUDE_PICKUP_TODAY)
        date_isoformat = self.config.get(CONF_DATE_ISOFORMAT)
        default_label = self.config.get(CONF_DEFAULT_LABEL)
        exclude_list = self.config.get(CONF_EXCLUDE_LIST)

        try:
            collector = MainCollector(
                provider,
                postal_code,
                street_number,
                suffix,
                username,
                password,
                exclude_pickup_today,
                date_isoformat,
                exclude_list,
                default_label,
            )
        except ValueError as err:
            _LOGGER.error(f"Collector initialization failed: {err}")
            return

        try:
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom
            _LOGGER.debug("Waste data updated successfully.")
        except ValueError as err:
            _LOGGER.error(f"Failed to fetch waste data: {err}")
            self.waste_data_with_today = self.waste_data_without_today = self.waste_data_custom = default_label
