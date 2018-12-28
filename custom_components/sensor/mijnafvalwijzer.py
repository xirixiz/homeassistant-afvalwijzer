"""
@ Authors     : Bram van Dartel
@ Date        : 28/12/2018
@ Description : MijnAfvalwijzer Sensor - It queries mijnafvalwijzer.nl.
"""
VERSION = '1.1.8'

from datetime import datetime, timedelta, date
import voluptuous as vol
import requests
import logging

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'mijnafvalwijzer'
DOMAIN = 'mijnafvalwijzer'
ICON = 'mdi:delete-empty'
SENSOR_PREFIX = 'trash_'

CONST_POSTCODE = "postcode"
CONST_HUISNUMMER = "huisnummer"
CONST_TOEVOEGING = "toevoeging"
CONST_DATEFORMAT = "datumformaat"
CONST_LABEL_NONE = "label_geen"

# Test values
# SCAN_INTERVAL = timedelta(seconds=60)
# MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SCAN_INTERVAL = timedelta(seconds=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=900)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONST_POSTCODE): cv.string,
    vol.Required(CONST_HUISNUMMER): cv.string,
    vol.Optional(CONST_TOEVOEGING, default=""): cv.string,
    vol.Optional(CONST_LABEL_NONE, default="Geen"): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    postcode = config.get(CONST_POSTCODE)
    huisnummer = config.get(CONST_HUISNUMMER)
    toevoeging = config.get(CONST_TOEVOEGING)
    url = ("https://json.mijnafvalwijzer.nl/?method=postcodecheck& \
            postcode={0}&street=&huisnummer={1}&toevoeging={2}& \
            platform=phone&langs=nl&").format(postcode, huisnummer, toevoeging)
    response = requests.get(url)
    json_obj = response.json()
    json_data = (json_obj['data']['ophaaldagen']['data'] + json_obj['data']['ophaaldagenNext']['data'])
    trashTotal = [{1: 'today'}, {2: 'tomorrow'}, {2: 'days_to_next_pickup'}]
    countIndex = len(trashTotal) + 1
    trashType = {}
    devices = []

    # Collect trash items
    for item in json_data:
        name = item["nameType"]
        if name not in trashType:
            trash = {}
            trashType[name] = item["nameType"]
            trash[countIndex] = item["nameType"]
            countIndex += 1
            trashTotal.append(trash)

    data = (TrashCollectionSchedule(url, trashTotal, config))

    for trash_type in trashTotal:
        for t in trash_type.values():
            devices.append(TrashCollectionSensor(t, data))
    add_devices(devices)


class TrashCollectionSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self.data = data

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
        self.data.update()
        for d in self.data.data:
            if d['key'] == self._name:
                self._state = d['value']


class TrashCollectionSchedule(object):
    """Fetch new state data for the sensor."""

    def __init__(self, url, trashTotal, config):
        """Fetch vars."""
        self._url = url
        self._trashTotal = trashTotal
        self.data = None
        self._config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        response = requests.get(self._url)
        json_obj = response.json()
        json_data = (json_obj['data']['ophaaldagen']['data'] + json_obj['data']['ophaaldagenNext']['data'])
        today = datetime.today().strftime("%Y-%m-%d")
        dateConvert = datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)
        tomorrow = datetime.strftime(dateConvert, "%Y-%m-%d")
        trash = {}
        trashType = {}
        trashInDays = {}
        trashToday = {}
        trashTomorrow = {}
        multiTrashToday = []
        multiTrashTomorrow = []
        tschedule = []

        labelNone = self._config.get(CONST_LABEL_NONE)

        def d(s):
            [year, month, day] = map(int, s.split('-'))
            return date(year, month, day)
        def days(start, end):
                return (d(end) - d(start)).days

        # Collect upcoming trash pickup dates
        for name in self._trashTotal:
            for item in json_data:
                name = item["nameType"]
                dateFormat = datetime.strptime(item['date'], "%Y-%m-%d")
                dateConvert = dateFormat.strftime("%Y-%m-%d")

                if name not in trashType:
                    if item['date'] >= today:
                        trash = {}
                        trashType[name] = item["nameType"]
                        trash['key'] = item['nameType']
                        trash['value'] = dateConvert
                        tschedule.append(trash)

                    if item['date'] > today:
                        if len(trashInDays) == 0:
                            trashType[name] = "next_in_days"
                            trashInDays['key'] = "next_in_days"
                            trashInDays['value'] = (days(today, dateConvert))
                            tschedule.append(trashInDays)

                    if item['date'] == today:
                        trashType[name] = "today"
                        trashToday['key'] = "today"
                        multiTrashToday.append(item['nameType'])
                        tschedule.append(trashToday)

                    if item['date'] == tomorrow:
                        trashType[name] = "tomorrow"
                        trashTomorrow['key'] = "tomorrow"
                        multiTrashTomorrow.append(item['nameType'])
                        tschedule.append(trashTomorrow)

        if len(trashInDays) == 0:
            trashType[name] = "next_in_days"
            trashInDays['key'] = 'next_in_days'
            trashInDays['value'] = labelNone
            tschedule.append(trashInDays)

        if len(multiTrashToday) == 0:
            trashToday = {}
            trashType[name] = "today"
            trashToday['key'] = "today"
            trashToday['value'] = labelNone
            tschedule.append(trashToday)
        else:
            trashToday['value'] = ', '.join(multiTrashToday)

        if len(multiTrashTomorrow) == 0:
            trashTomorrow = {}
            trashType[name] = "tomorrow"
            trashTomorrow['key'] = "tomorrow"
            trashTomorrow['value'] = labelNone
            tschedule.append(trashTomorrow)
        else:
            trashTomorrow['value'] = ', '.join(multiTrashTomorrow)

        for item in json_data:
            name = item["nameType"]
            if name not in trashType:
                trash = {}
                trashType[name] = item["nameType"]
                trash['key'] = item['nameType']
                trash['value'] = labelNone
                tschedule.append(trash)

        self.data = tschedule
