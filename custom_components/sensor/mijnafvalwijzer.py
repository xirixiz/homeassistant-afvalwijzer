"""
@ Author      : Bram van Dartel
@ Date        : 28/03/2018
@ Description : MijnAfvalwijzer Sensor - It queries mijnafvalwijzer.nl.
@ Notes:        Copy this file and place it in your
                "Home Assistant Config folder\custom_components\sensor\" folder.
"""
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
from homeassistant.util import Throttle

from urllib.request import urlopen
from datetime import timedelta
import json
import argparse
import datetime
import logging

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:delete-empty'

TRASH_TYPES = [{1: "gft"}, {2: "pmd"}, {3: "papier"}, {4: "restafval"}]

SCAN_INTERVAL = timedelta(seconds=60)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=28800)

DEFAULT_NAME = 'MijnAfvalwijzer Sensor'
SENSOR_PREFIX = 'trash_'
CONST_POSTCODE = "postcode"
CONST_HUISNUMMER = "huisnummer"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONST_POSTCODE): cv.string,
    vol.Required(CONST_HUISNUMMER): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up date afval sensor."""
    postcode = config.get(CONST_POSTCODE)
    huisnummer = config.get(CONST_HUISNUMMER)
    url = ("http://json.mijnafvalwijzer.nl/?"
       "method=postcodecheck&postcode={0}&street=&huisnummer={1}&toevoeging=&platform=phone&langs=nl&").format(postcode,huisnummer)
    data = TrashCollectionSchedule(url, TRASH_TYPES)

    devices = []
    for trash_type in TRASH_TYPES:
        #print(trash_type.values())
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
        """Return the icon to use in the frontend."""
        return ICON

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        #print(self.data.data)
        for d in self.data.data:
            if d['name_type'] == self._name:
                self._state = d['pickup_date']

class TrashCollectionSchedule(object):

    def __init__(self, url, trash_types):
        self._url = url
        self._trash_types = trash_types
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        response = urlopen(self._url)
        string = response.read().decode('utf-8')
        json_obj = json.loads(string)
        json_data = json_obj['data']['ophaaldagen']['data']
        json_data_next = json_obj['data']['ophaaldagenNext']['data']
        today = datetime.date.today().strftime("%Y-%m-%d")
        trashType = {}
        tschedule = []

        for name in TRASH_TYPES:
            for item in json_data or json_data_next:
                name = item["nameType"]
                d = datetime.datetime.strptime(item['date'], "%Y-%m-%d")
                dateConvert = d.strftime("%Y-%m-%d")                
                if name not in trashType:
                    if item['date'] > today:
                        trash = {}
                        trashType[name] = item["nameType"]
                        trash['name_type'] = item['nameType']
                        trash['pickup_date'] = dateConvert
                        tschedule.append(trash)
                        self.data = tschedule