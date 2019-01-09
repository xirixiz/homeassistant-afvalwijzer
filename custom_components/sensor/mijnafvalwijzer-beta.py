"""
@ Authors     : Bram van Dartel
@ Date        : 05/01/2019
@ Description : MijnAfvalwijzer Sensor - It queries mijnafvalwijzer.nl.

- platform: mijnafvalwijzer
  postcode: POSTAL_CODE
  huisnummer: HOUSE_NUMBER
  toevoeging: a, b, c
  label_none: none, geen
"""

VERSION = '2.0.0'

from datetime import datetime, timedelta, date
import voluptuous as vol
import requests
import sys
import logging
import json

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'mijnafvalwijzer'
DEFAULT_TIMEOUT = 10
DEFAULT_LABEL = 'Geen'

DOMAIN = 'mijnafvalwijzer'
ICON = 'mdi:delete-empty'
SENSOR_PREFIX = 'trash_'

CONST_POSTCODE = 'postcode'
CONST_HUISNUMMER = 'huisnummer'
CONST_TOEVOEGING = 'toevoeging'
CONST_LABEL_NONE = 'label_geen'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONST_POSTCODE): cv.string,
    vol.Required(CONST_HUISNUMMER): cv.string,
    vol.Optional(CONST_TOEVOEGING, default=''): cv.string,
    vol.Optional(CONST_LABEL_NONE, default=DEFAULT_LABEL): cv.string,
})

SCAN_INTERVAL = timedelta(seconds=10)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mijnafvalwijzer sensor platform."""

    # Request JSON
    postcode = config.get(CONST_POSTCODE)
    huisnummer = config.get(CONST_HUISNUMMER)
    toevoeging = config.get(CONST_TOEVOEGING)

    if None in (postcode, huisnummer):
        _LOGGER.error("Mijnafvalwijzer - postcode or huisnummer not set in HomeAssistant config")
        return False
    else:
        _LOGGER.debug("Initializing mijnafvalwijzer sensor postcode: %s, huisnummer: %s", postcode, huisnummer)

    url = ("https://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode={0}&street=&huisnummer={1}&toevoeging={2}&platform=phone&langs=nl&").format(postcode, huisnummer, toevoeging)
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)

    if response.status_code != requests.codes.ok:
        _LOGGER.exception("Error doing API request")
    else:
        _LOGGER.debug("API request ok %d", response.status_code)

    json_obj = response.json()
    json_data = (json_obj['data']['ophaaldagen']['data'] + json_obj['data']['ophaaldagenNext']['data'])

    if len(json_data) == 0:
        _LOGGER.error("JSON object doens't contain data")
    else:
        _LOGGER.debug("JSON object contains data")

    # Remove unused elements from json object
    for x in json_data:
        if 'type' in x:
            del x['type']
    _LOGGER.debug("Removed type element from JSON object")


    # Fetch trash types
    size=len(json_data)
    uniqueTrashNames = ['today', 'tomorrow', 'next']
    today = datetime.today().strftime("%Y-%m-%d")
    dateConvert = datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)
    tomorrow = datetime.strftime(dateConvert, "%Y-%m-%d")
    trashSchedule = []
    devices = []

    for i in range(0,size,1):
        if(json_data[i]['nameType'] not in uniqueTrashNames):
             if json_data[i]['date'] >= today:
               uniqueTrashNames.append(json_data[i]['nameType'])
               trashSchedule.append(json_data[i])

    _LOGGER.debug("uniqueTrashNames succesfully added: %s", uniqueTrashNames)
    _LOGGER.debug("trashSchedule succesfully added: %s", trashSchedule)

    data = (TrashCollectionSchedule(config, json_data, trashSchedule, today, tomorrow))

    for item in uniqueTrashNames:
        devices.append(TrashCollectionSensor(item, data))
    add_devices(devices)

    _LOGGER.debug("JSON object succesfully added: %s", devices)

class TrashCollectionSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._data = data

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

    def update(self):
        """Fetch new state data for the sensor."""
        self._data.update()
        for x in self._data._data:
            if x['nameType'] == self._name:
                self._state = x['date']

        _LOGGER.debug("Update called for mijnafvalwijzer")


class TrashCollectionSchedule(object):
    """Fetch new state data for the sensor."""

    def __init__(self, config, json_data, trashSchedule, today, tomorrow):
        """Fetch vars."""
        self._data = None
        self._config = config
        self._json_data = json_data
        self._trashSchedule = trashSchedule
        self._today = today
        self._tomorrow = tomorrow

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        # Append Today data
        trashToday = {}
        multiTrashToday = []
        today_out = [x for x in self._trashSchedule if x['date'] == self._today]
        _LOGGER.debug("Trash Today: %s", today_out)
        if len(today_out) == 0:
            trashToday['nameType'] = 'today'
            trashToday['date'] = 'None'
            self._trashSchedule.append(trashToday)
            _LOGGER.debug("Today contains no data, skipping")
        else:
            for x in today_out:
                trashToday['nameType'] = 'today'
                multiTrashToday.append(x['nameType'])
            self._trashSchedule.append(trashToday)
            trashToday['date'] = ', '.join(multiTrashToday)
            _LOGGER.debug("Today data succesfully added %s", trashToday)

        # Append Tomorrow data
        trashTomorrow = {}
        multiTrashTomorrow = []
        tomorrow_out = [x for x in self._trashSchedule if x['date'] == self._tomorrow]
        _LOGGER.debug("Trash Tomorrow: %s", tomorrow_out)
        if len(tomorrow_out) == 0:
            trashTomorrow['nameType'] = 'tomorrow'
            trashTomorrow['date'] = 'None'
            self._trashSchedule.append(trashTomorrow)
            _LOGGER.debug("Tomorrow contains no data, skipping")
        else:
            for x in tomorrow_out:
                trashTomorrow['nameType'] = 'tomorrow'
                multiTrashTomorrow.append(x['nameType'])
            self._trashSchedule.append(trashTomorrow)
            trashTomorrow['date'] = ', '.join(multiTrashTomorrow)
            _LOGGER.debug("Tomorrow data succesfully added %s", trashTomorrow)

        # Append next pickup in days
        trashNext = {}
        next_out = [x for x in self._trashSchedule if x['date'] > self._today]
        _LOGGER.debug("Trash Next: %s", next_out)
        def d(s):
            [year, month, day] = map(int, s.split('-'))
            return date(year, month, day)
        def days(start, end):
            return (d(end) - d(start)).days

        if len(next_out) == 0:
           trashNext['nameType'] = 'next'
           trashNext['date'] = 'None'
           self._trashSchedule.append(trashNext)
           _LOGGER.debug("Next contains no data, skupping")
        else:
            dateFormat = datetime.strptime(next_out[0]['date'], "%Y-%m-%d")
            dateConvert = dateFormat.strftime("%Y-%m-%d")
            if len(trashNext) == 0:
                trashNext['nameType'] = 'next'
                trashNext['date'] = (days(self._today, dateConvert))
                self._trashSchedule.append(trashNext)
                _LOGGER.debug("Next data succesfully added %s", trashNext)

        _LOGGER.debug("trashSchedule content %s", self._trashSchedule)
        self._data = self._trashSchedule
