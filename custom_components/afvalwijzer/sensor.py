"""
@ Authors     : Bram van Dartel
@ Description : Afvalwijzer Json/Scraper Sensor - It queries mijnafvalwijzer.nl or afvalstoffendienstkalender.nl.
"""

VERSION = '4.1.2'

from Afvaldienst import Afvaldienst
from datetime import date, datetime, timedelta
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'afvalwijzer'
DOMAIN = 'afvalwijzer'
ICON = 'mdi:delete-empty'
SENSOR_PREFIX = 'trash_'

CONST_PROVIDER = 'provider'
CONST_ZIPCODE = 'zipcode'
CONST_HOUSENUMBER = 'housenumber'
CONST_SUFFIX = 'suffix'
CONST_LABEL = 'default_label'

PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONST_PROVIDER, default="mijnafvalwijzer"): cv.string,
    vol.Required(CONST_ZIPCODE): cv.string,
    vol.Required(CONST_HOUSENUMBER): cv.string,
    vol.Optional(CONST_SUFFIX, default=""): cv.string,
    vol.Optional(CONST_LABEL, default="Geen"): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the sensor platform."""
    provider = config.get(CONST_PROVIDER)
    zipcode = config.get(CONST_ZIPCODE)
    housenumber = config.get(CONST_HOUSENUMBER)
    suffix = config.get(CONST_SUFFIX)

    afvaldienst = Afvaldienst(provider, zipcode, housenumber, suffix)

    # Get trash types to create sensors from
    trashTypesDefault = afvaldienst.trash_type_list
    trashTypesAdditional = afvaldienst.trash_schedule_today_json + afvaldienst.trash_schedule_tomorrow_json + afvaldienst.trash_schedule_next_days_json + afvaldienst.trash_schedule_next_item_json + afvaldienst.trash_schedule_next_date_json + afvaldienst.trash_schedule_dat_json
    for item in trashTypesAdditional:
        trashTypesDefault.append(item['key'])

    fetch_trash_data = (TrashSchedule(config))

    # Setup sensors
    sensors = []
    for name in trashTypesDefault:
        sensors.append(TrashSensor(hass, name, fetch_trash_data, afvaldienst, config))
    async_add_entities(sensors)


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
        self._fetch_trash_data.update()
        self._state = self._config.get(CONST_LABEL)

        for item in self._fetch_trash_data.trash_schedule_default:
            attributes = {}
            attributes['next_pickup_in_days'] = item['days_remaining']
            if item['key'] == self._name:
                self._state = item['value']
                self._attributes = attributes

        for item in self._fetch_trash_data.trash_schedule_additional:
            if item['key'] == self._name:
                if item['value'] != 'None':
                    self._state = item['value']

        for item in self._fetch_trash_data.trash_schedule_firstwastetype:
            if item['key'] == self._name:
                self._state = item['value']

        for item in self._fetch_trash_data.trash_schedule_firstwastedate:
            if item['key'] == self._name:
                self._state = item['value']


class TrashSchedule(object):
    """Fetch new state data for the sensor."""
    def __init__(self, config):
        """Fetch vars."""
        self._config = config

    def update(self):
        """Fetch new state data for the sensor."""
        provider = self._config.get(CONST_PROVIDER)
        zipcode = self._config.get(CONST_ZIPCODE)
        housenumber = self._config.get(CONST_HOUSENUMBER)
        suffix = self._config.get(CONST_SUFFIX)
        afvaldienst = Afvaldienst(provider, zipcode, housenumber, suffix)

        self.trash_schedule_default = afvaldienst.trash_schedulefull_json
        self.trash_schedule_additional = afvaldienst.trash_schedule_today_json + afvaldienst.trash_schedule_tomorrow_json + afvaldienst.trash_schedule_next_days_json + afvaldienst.trash_schedule_dat_json
        self.trash_schedule_firstwastetype = afvaldienst.trash_schedule_next_item_json
        self.trash_schedule_firstwastedate = afvaldienst.trash_schedule_next_date_json