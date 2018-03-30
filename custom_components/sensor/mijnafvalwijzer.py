"""
@ Authors     : Bram van Dartel & Daniel Palstra
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

from datetime import timedelta
import requests
import json
import argparse
import datetime
import logging

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=28800)
DEFAULT_NAME = 'MijnAfvalwijzer Sensor'
ICON = 'mdi:delete-empty'
SENSOR_PREFIX = 'trash_'
CONST_POSTCODE = "postcode"
CONST_HUISNUMMER = "huisnummer"
CONST_TOEVOEGING = "toevoeging"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONST_POSTCODE): cv.string,
    vol.Required(CONST_HUISNUMMER): cv.string,
    vol.Optional(CONST_TOEVOEGING, default=""): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    postcode = config.get(CONST_POSTCODE)
    huisnummer = config.get(CONST_HUISNUMMER)
    toevoeging = config.get(CONST_TOEVOEGING)
    url = ("http://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode={0}&street=&huisnummer={1}&toevoeging={2}&platform=phone&langs=nl&").format(postcode,huisnummer,toevoeging)    
    response = requests.get(url)
    json_obj = response.json()
    json_data = json_obj['data']['ophaaldagen']['data']
    json_data_next = json_obj['data']['ophaaldagenNext']['data']
    today = datetime.date.today().strftime("%Y-%m-%d")
    countType = 1
    trashType = {}
    trashTotal = []
    devices = []

    # Collect trash items
    for item in json_data or json_data_next:
        name = item["nameType"]
        if name not in trashType:
                trash = {}
                trashType[name] = item["nameType"]
                trash[countType] = item["nameType"]
                countType +=1
                trashTotal.append(trash)

    data = TrashCollectionSchedule(json_data, json_data_next, today, trashTotal)
    
    for trash_type in trashTotal:
        for t in trash_type.values():
            devices.append(TrashCollectionSensor(t, data))
    add_devices(devices)

    
class TrashCollectionSensor(Entity):
    def __init__(self, name, data):
        self._state = None
        self._name = name
        self.data = data

    @property
    def name(self):
        return SENSOR_PREFIX + self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return ICON

    def update(self):
        self.data.update()
        for d in self.data.data:
            if d['name_type'] == self._name:
                self._state = d['pickup_date']


class TrashCollectionSchedule(object):
    def __init__(self, json_data, json_data_next, today, trashTotal):
        self._json_data = json_data
        self._json_data_next = json_data_next
        self._today = today
        self._trashTotal = trashTotal
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        json_data = self._json_data
        json_data_next = self._json_data_next
        today = self._today
        trashTotal = self._trashTotal
        trashType = {}
        tschedule = []

        # Collect upcoming trash pickup dates
        for name in trashTotal:
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