"""
@ Authors     : Bram van Dartel
@ Description : Afvalwijzer Json/Scraper Sensor - It queries mijnafvalwijzer.nl or afvalstoffendienstkalender.nl.
"""

VERSION = "4.4.1"

import asyncio
import logging
from datetime import date, datetime, timedelta
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from Afvaldienst import Afvaldienst
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "afvalwijzer"
DOMAIN = "afvalwijzer"
ICON = "mdi:delete-empty"
SENSOR_PREFIX = "trash_"

CONST_PROVIDER = "provider"
CONST_API_TOKEN = "api_token"
CONST_ZIPCODE = "zipcode"
CONST_HOUSENUMBER = "housenumber"
CONST_SUFFIX = "suffix"
CONST_COUNT_TODAY = "count_today"
CONST_LABEL = "default_label"

SCAN_INTERVAL = timedelta(seconds=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3600)
PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONST_PROVIDER, default="mijnafvalwijzer"): cv.string,
        vol.Optional(CONST_API_TOKEN, default=""): cv.string,
        vol.Required(CONST_ZIPCODE): cv.string,
        vol.Required(CONST_HOUSENUMBER): cv.string,
        vol.Optional(CONST_SUFFIX, default=""): cv.string,
        vol.Optional(CONST_COUNT_TODAY, default="false"): cv.string,
        vol.Optional(CONST_LABEL, default="Geen"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the sensor platform."""
    provider = config.get(CONST_PROVIDER)
    api_token = config.get(CONST_API_TOKEN)
    zipcode = config.get(CONST_ZIPCODE)
    housenumber = config.get(CONST_HOUSENUMBER)
    suffix = config.get(CONST_SUFFIX)
    count_today = config.get(CONST_COUNT_TODAY)

    _LOGGER.debug("Afvalwijzer provider = %s", provider)
    _LOGGER.debug("Afvalwijzer api_token = %s", api_token)
    _LOGGER.debug("Afvalwijzer zipcode = %s", zipcode)
    _LOGGER.debug("Afvalwijzer housenumber = %s", housenumber)

    try:
        afvaldienst = await hass.async_add_executor_job(
            partial(
                Afvaldienst,
                provider,
                api_token,
                zipcode,
                housenumber,
                suffix,
                count_today,
            )
        )
    except ValueError as err:
        _LOGGER.error("Check afvaldienst platform settings %s", err.args)
        raise

    # Get trash types to create sensors from
    trash_types = afvaldienst.trash_types_from_schedule
    _LOGGER.debug("Trash type list = %s", trash_types)

    # Fetch all trash data
    fetch_trash_data = TrashSchedule(config)

    # Setup sensors
    sensors = []
    for name in trash_types:
        sensors.append(TrashSensor(hass, name, fetch_trash_data, afvaldienst, config))
    async_add_entities(sensors)

    _LOGGER.debug("Sensors = %s", sensors)


class TrashSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, name, fetch_trash_data, afvaldienst, config):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._fetch_trash_data = fetch_trash_data
        self._afvaldienst = afvaldienst
        self._attributes = {}
        self._config = config
        self._state = self._config.get(CONST_LABEL)

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_PREFIX + self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Set the default sensor icon."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attributes

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self._hass.async_add_executor_job(self._fetch_trash_data.update)
        self._state = self._config.get(CONST_LABEL)

        for x in self._fetch_trash_data.trash_schedule:
            attributes = {}
            attributes["next_pickup_in_days"] = x["days_remaining"]
            if x["key"] == self._name:
                self._state = x["value"]
                self._attributes = attributes

        for x in self._fetch_trash_data.trash_schedule_custom:
            if x["key"] == self._name:
                self._state = x["value"]


class TrashSchedule(object):
    """Fetch new state data for the sensor."""

    def __init__(self, config):
        """Fetch vars."""
        self._config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        provider = self._config.get(CONST_PROVIDER)
        api_token = self._config.get(CONST_API_TOKEN)
        zipcode = self._config.get(CONST_ZIPCODE)
        housenumber = self._config.get(CONST_HOUSENUMBER)
        suffix = self._config.get(CONST_SUFFIX)
        count_today = self._config.get(CONST_COUNT_TODAY)

        try:
            afvaldienst = Afvaldienst(
                provider, api_token, zipcode, housenumber, suffix, count_today
            )
        except ValueError as err:
            _LOGGER.error("Check afvaldienst platform settings %s", err.args)
            raise

        try:
            self.trash_schedule = afvaldienst.trash_schedule
            _LOGGER.debug("Data trash_schedule = %s", self.trash_schedule)
        except ValueError as err:
            _LOGGER.error("Check trash_schedule %s", err.args)
            self.trash_schedule = self._config.get(CONST_LABEL)
            raise

        try:
            self.trash_schedule_custom = afvaldienst.trash_schedule_custom
            _LOGGER.debug("Data trash_schedule_custom = %s", self.trash_schedule_custom)
        except ValueError as err:
            _LOGGER.error("Check trash_schedule_custom %s", err.args)
            self.trash_schedule_custom = self._config.get(CONST_LABEL)
            raise
