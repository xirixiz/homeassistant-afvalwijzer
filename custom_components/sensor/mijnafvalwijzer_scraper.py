"""
@ Authors     : Bram van Dartel
@ Date        : 13/01/2019
@ Description : MijnAfvalwijzer Scrape Sensor - It queries mijnafvalwijzer.nl.
"""
VERSION = '2.0.4'

import itertools
import logging
import re
from datetime import date, datetime, timedelta

import requests

import bs4
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'mijnafvalwijzer'
DOMAIN = 'mijnafvalwijzer'
ICON = 'mdi:delete-empty'
SENSOR_PREFIX = 'trash_'

CONST_POSTCODE = "postcode"
CONST_HUISNUMMER = "huisnummer"
CONST_TOEVOEGING = "toevoeging"
CONST_LABEL_NONE = "label_geen"

SCAN_INTERVAL = timedelta(seconds=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3600)

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
    url = ("https://www.mijnafvalwijzer.nl/nl/{0}/{1}/{2}").format(postcode, huisnummer, toevoeging)

    response = requests.get(url)
    if response.status_code != requests.codes.ok:
        _LOGGER.exception("Error doing API request")
    else:
        _LOGGER.debug("API request ok %d", response.status_code)

    soup = bs4.BeautifulSoup(response.text, "html.parser")
    if len(soup) == 0:
        _LOGGER.error("Respons doesn't contain data")
    else:
        _LOGGER.debug("Respons contains data")

    # Get trash shortname
    trashShortNames = []
    uniqueTrashShortNames = []
    defaultTrashNames = ['today', 'tomorrow', 'next']
    uniqueTrashShortNames.extend(defaultTrashNames)
    sensors = []
    try:
        for element in soup.select('a[href*="#waste"] p[class]'):
            trashShortNames.extend(element["class"])
        for element in trashShortNames:
            if element not in uniqueTrashShortNames:
                uniqueTrashShortNames.append(element)
    except IndexError:
        return 'Error, empty reply.'

    _LOGGER.debug("trashShortNames succesfully added: %s", trashShortNames)
    _LOGGER.debug("uniqueTrashShortNames succesfully added: %s", uniqueTrashShortNames)

    data = (TrashCollectionSchedule(url, defaultTrashNames ,config))

    try:
        for name in uniqueTrashShortNames:
            sensors.append(TrashCollectionSensor(name, data, config))
        add_devices(sensors)
    except IndexError:
        return 'Error, empty reply.'

    _LOGGER.debug("Object succesfully added as sensor(s): %s", sensors)


class TrashCollectionSensor(Entity):
    """Representation of a Sensor."""
    def __init__(self, name, data, config):
        """Initialize the sensor."""
        self.config = config
        self._state = self.config.get(CONST_LABEL_NONE)
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
        self._state = self.config.get(CONST_LABEL_NONE)

        _LOGGER.debug("Update called for mijnafvalwijzer...")

        try:
            for item in self.data.data:
                if item['key'] == self._name:
                    self._state = item['value']
        except IndexError:
            return 'Error, empty reply.'


class TrashCollectionSchedule(object):
    """Fetch new state data for the sensor."""
    def __init__(self, url, defaultTrashNames, config):
        """Fetch vars."""
        self.url = url
        self.data = None
        self.defaultTrashNames = defaultTrashNames
        self.config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        response = requests.get(self.url)
        if response.status_code != requests.codes.ok:
            _LOGGER.exception("Error doing API request")
        else:
            _LOGGER.debug("API request ok %d", response.status_code)

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        if len(soup) == 0:
            _LOGGER.error("Respons doesn't contain data")
        else:
            _LOGGER.debug("Respons contains data")

        today = datetime.today().strftime("%d-%m-%Y")
        today_date = datetime.strptime(today, "%d-%m-%Y")
        dateConvert = datetime.strptime(today, "%d-%m-%Y") + timedelta(days=1)
        tomorrow = datetime.strftime(dateConvert, "%d-%m-%Y")
        tomorrow_date = datetime.strptime(tomorrow, "%d-%m-%Y")
        labelNone = self.config.get(CONST_LABEL_NONE)

        # Convert month to month number function
        def _get_month_number(month):
            if month == 'januari':
                return '01'
            elif month == 'februari':
                return '02'
            elif month == 'maart':
                return '03'
            elif month == 'april':
                return '04'
            elif month == 'mei':
                return '05'
            elif month == 'juni':
                return '06'
            elif month == 'juli':
                return '07'
            elif month == 'augustus':
                return '08'
            elif month == 'september':
                return '09'
            elif month == 'oktober':
                return '10'
            elif month == 'november':
                return '11'
            elif month == 'december':
                return '12'
            else:
                return '00'

        # Get current year
        for item in soup.select('[class="ophaaldagen"]'):
            year_id = item["id"]
        year = re.sub('jaar-','',year_id)
        _LOGGER.debug("Year found: %s", year)

        # Get trash dump
        trashDump = []
        trashSchedule = []
        json_data = []
        try:
            for data in soup.select('a[href*="#waste"] p[class]'):
                element = data["class"]
                for item in element:
                    x = item
                name = data.get_text()
                trashDump.append(name)
                trashDump.append(x)
                _LOGGER.debug("Trash scraped from website: %s", trashDump)
        except IndexError:
            return 'Error, empty reply.'

        # Get trash dates and generate dictionairy
        uniqueTrashDates = [i.split('\n', 1) for i in trashDump]
        uniqueTrashDates = list(itertools.chain.from_iterable(uniqueTrashDates))
        uniqueTrashDates = [uniqueTrashDates[i:i+3]for i in range(0,len(uniqueTrashDates),3)]
        _LOGGER.debug("Trash dates conversion output from scraped website data: %s", uniqueTrashDates)

        try:
            for item in uniqueTrashDates:
                split_date = item[0].split(' ')
                day = split_date[1]
                month_name = split_date[2]
                month = _get_month_number(month_name)
                _LOGGER.debug("Converting month name: %s to month number %s", month_name, month)
                trashDump = {}
                trashDump['key'] = item[2]
                trashDump['description'] = item[1]
                trashDump['value'] = day + '-' + month + '-' + year
                json_data.append(trashDump)
                _LOGGER.debug("New generated dictionairy with converted dates: %s", json_data)
        except IndexError:
            return 'Error, empty reply.'


        # Append first upcoming unique trash item with pickup date
        uniqueTrashNames = []
        uniqueTrashNames.extend(self.defaultTrashNames)
        try:
            for item in json_data:
                key = item['key']
                description = item['description']
                value = item['value']
                value_date = datetime.strptime(item['value'], "%d-%m-%Y")
                if value_date >= today_date:
                    if key not in uniqueTrashNames:
                        trash = {}
                        trash['key'] = key
                        trash['description'] = description
                        trash['value'] = value
                        uniqueTrashNames.append(key)
                        trashSchedule.append(trash)
                        _LOGGER.debug("New dictionairy with update data: %s", trashSchedule)
        except IndexError:
            return 'Error, empty reply.'


        # Collect data
        today_out = [x for x in trashSchedule if datetime.strptime(x['value'], "%d-%m-%Y") == today_date]
        _LOGGER.debug("Trash Today: %s", today_out)
        tomorrow_out = [x for x in trashSchedule if datetime.strptime(x['value'], "%d-%m-%Y") == tomorrow_date]
        _LOGGER.debug("Trash Tomorrow: %s", tomorrow_out)
        next_out = [x for x in trashSchedule if datetime.strptime(x['value'], "%d-%m-%Y") > today_date]
        _LOGGER.debug("Trash Next Pickup Day: %s", next_out)

        # Append Today data
        trashToday = {}
        multiTrashToday = []
        if len(today_out) == 0:
            trashToday['key'] = 'today'
            trashToday['description'] = 'Trash Today'
            trashToday['value'] = labelNone
            trashSchedule.append(trashToday)
            _LOGGER.debug("Today contains no data, skipping...")
        else:
            try:
                for x in today_out:
                    trashToday['key'] = 'today'
                    trashToday['description'] = 'Trash Today'
                    multiTrashToday.append(x['key'])
                trashSchedule.append(trashToday)
                trashToday['value'] = ', '.join(multiTrashToday)
                _LOGGER.debug("Today data succesfully added %s", trashToday)
            except IndexError:
                return 'Error, empty reply.'


        # Append Tomorrow data
        trashTomorrow = {}
        multiTrashTomorrow = []
        if len(tomorrow_out) == 0:
            trashTomorrow['key'] = 'tomorrow'
            trashTomorrow['description'] = 'Trash Tomorrow'
            trashTomorrow['value'] = labelNone
            trashSchedule.append(trashTomorrow)
            _LOGGER.debug("Tomorrow contains no data, skipping...")
        else:
            try:
                for x in tomorrow_out:
                    trashTomorrow['key'] = 'tomorrow'
                    trashTomorrow['description'] = 'Trash Tomorrow'
                    multiTrashTomorrow.append(x['key'])
                trashSchedule.append(trashTomorrow)
                trashTomorrow['value'] = ', '.join(multiTrashTomorrow)
                _LOGGER.debug("Today data succesfully added %s", trashTomorrow)
            except IndexError:
                return 'Error, empty reply.'


        # Append next pickup in days
        trashNext = {}
        ## Amount of days between two dates function
        def d(s):
            [year, month, day] = map(int, s.split('-'))
            return date(day, month, year)
        def days(start, end):
            return (d(end) - d(start)).days

        if len(next_out) == 0:
            trashNext['key'] = 'next'
            trashNext['value'] = labelNone
            trashSchedule.append(trashNext)
            _LOGGER.debug("Next contains no data, skipping...")
        else:
            if len(trashNext) == 0:
                trashNext['key'] = 'next'
                trashNext['value'] = (days(today, next_out[0]['value']))
                trashSchedule.append(trashNext)
                _LOGGER.debug("Next data succesfully added %s", trashNext)


        # Return collected data
        _LOGGER.debug("trashSchedule content %s", trashSchedule)
        self.data = trashSchedule
