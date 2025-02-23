import requests
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.sensor import PLATFORM_SCHEMA
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .collector.main_collector import MainCollector
from .collector.clean_collector import CleanCollector
from .const.const import (
    _LOGGER,
    CONF_COLLECTOR,
    CONF_CLEANCOLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_DATE_ISOFORMAT,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    CONF_USERNAME,
    CONF_PASSWORD,
    SCAN_INTERVAL,
)
from .sensor_custom import CustomSensor
from .sensor_provider import ProviderSensor

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COLLECTOR, default="mijnafvalwijzer"): cv.string,
        vol.Optional(CONF_CLEANCOLLECTOR, default=""): cv.string,
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_STREET_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_USERNAME, default=""): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
        vol.Optional(CONF_DATE_ISOFORMAT, default=False): cv.boolean,
        vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    if not discovery_info:
        _LOGGER.error("No discovery information provided; sensors cannot be created.")
        return
    await _setup_sensors(hass, discovery_info, async_add_entities)

async def async_setup_entry(hass, entry, async_add_entities):
    await _setup_sensors(hass, entry.data, async_add_entities)

async def _setup_sensors(hass, config, async_add_entities):
    provider = config.get(CONF_COLLECTOR)
    container_cleaning_provider = config.get(CONF_CLEANCOLLECTOR)
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

    # Initialize data handlers
    data = AfvalwijzerData(hass, config)
    clean_data = ContainerCleaningData(hass, config) if container_cleaning_provider else None
    
    await hass.async_add_executor_job(data.update)
    if clean_data:
        await hass.async_add_executor_job(clean_data.update)
    
    update_interval = timedelta(hours=4)
    def schedule_update(_):
        hass.loop.call_soon_threadsafe(hass.async_add_executor_job, data.update)
        if clean_data:
            hass.loop.call_soon_threadsafe(hass.async_add_executor_job, clean_data.update)
    
    async_track_time_interval(hass, schedule_update, update_interval)

    try:
        waste_types_provider = set(data.waste_data_with_today.keys())
        waste_types_custom = set(data.waste_data_custom.keys())

        if clean_data:
            data.waste_data_with_today.update(clean_data.waste_data_with_today)
            waste_types_provider.update(clean_data.waste_data_with_today.keys())

    except Exception as err:
        _LOGGER.error(f"Failed to fetch waste types: {err}")
        return

    entities = [
        ProviderSensor(hass, waste_type, data, clean_data, config) for waste_type in waste_types_provider
    ] + [
        CustomSensor(hass, waste_type, data, config) for waste_type in waste_types_custom
    ]

    
    if not entities:
        _LOGGER.error("No entities created; check configuration or collector output.")
        return
    
    _LOGGER.info(f"Adding {len(entities)} sensors for Afvalwijzer.")
    async_add_entities(entities, True)

class AfvalwijzerData:
    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.waste_data_with_today = {}
        self.waste_data_without_today = {}
        self.waste_data_custom = {}

    def update(self):
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
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom

            #_LOGGER.debug(f"AFV: {self.waste_data_custom}")
            _LOGGER.debug("Waste data updated successfully.")
        except ValueError as err:
            _LOGGER.error(f"Failed to fetch waste data: {err}")

class ContainerCleaningData:
    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.waste_data_with_today = {}
        self.waste_data_without_today = {}
        self.waste_data_custom = {}

    def update(self):
        try:
            collector = CleanCollector(
                self.config.get(CONF_CLEANCOLLECTOR),
                self.config.get(CONF_POSTAL_CODE),
                self.config.get(CONF_STREET_NUMBER),
                self.config.get(CONF_SUFFIX),
                self.config.get(CONF_EXCLUDE_PICKUP_TODAY),
                self.config.get(CONF_DATE_ISOFORMAT),
                self.config.get(CONF_EXCLUDE_LIST),
                self.config.get(CONF_DEFAULT_LABEL),
            )
            self.waste_data_with_today = collector.waste_data_with_today
            self.waste_data_without_today = collector.waste_data_without_today
            self.waste_data_custom = collector.waste_data_custom

            #_LOGGER.debug(f"CCD: {self.waste_data_custom}")
            _LOGGER.debug("Container cleaning data updated successfully.")
        except ValueError as err:
            _LOGGER.error(f"Failed to fetch container cleaning data: {err}")
