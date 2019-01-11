"""
@ Authors     : Bram van Dartel
@ Date        : 12/01/2019
@ Description : MijnAfvalwijzer Scrape Sensor - It queries mijnafvalwijzer.nl.
"""
VERSION = '2.0.2'

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
    soup = bs4.BeautifulSoup(response.text, "html.parser")

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
        return 'No matching trashtype(s) found.'

    data = (TrashCollectionSchedule(url, defaultTrashNames ,config))

    for name in uniqueTrashShortNames:
        sensors.append(TrashCollectionSensor(name, data, config))
    add_devices(sensors)


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
        for item in self.data.data:
            if item['key'] == self._name:
                self._state = item['value']


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
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        today = datetime.today().strftime("%d-%m-%Y")
        dateConvert = datetime.strptime(today, "%d-%m-%Y") + timedelta(days=1)
        tomorrow = datetime.strftime(dateConvert, "%d-%m-%Y")
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
                return None

        # Get current year
        for item in soup.select('[class="ophaaldagen"]'):
            year_id = item["id"]
        year = re.sub('jaar-','',year_id)

        # Get trash date
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
        except IndexError:
            return 'Error, empty reply.'

        uniqueTrashDates = [i.split('\n', 1) for i in trashDump]
        uniqueTrashDates = list(itertools.chain.from_iterable(uniqueTrashDates))
        uniqueTrashDates = [uniqueTrashDates[i:i+3]for i in range(0,len(uniqueTrashDates),3)]

        try:
            for item in uniqueTrashDates:
                split_date = item[0].split(' ')
                day = split_date[1]
                month_name = split_date[2]
                month = _get_month_number(month_name)
                trashDump = {}
                trashDump['key'] = item[2]
                trashDump['description'] = item[1]
                trashDump['value'] = day + '-' + month + '-' + year
                json_data.append(trashDump)
        except IndexError:
            return 'Error, empty reply.'


        # Append first upcoming unique trash item with pickup date
        size=len(json_data)
        uniqueTrashNames = []
        uniqueTrashNames.extend(self.defaultTrashNames)

        for i in range(0,size,1):
            if(json_data[i]['key'] not in uniqueTrashNames):
                if json_data[i]['value'] >= today:
                    uniqueTrashNames.append(json_data[i]['key'])
                    trashSchedule.append(json_data[i])


        # Append Today data
        trashToday = {}
        multiTrashToday = []
        today_out = [x for x in trashSchedule if x['value'] == today and x['key'] not in self.defaultTrashNames]
        if len(today_out) == 0:
            trashToday['key'] = 'today'
            trashToday['description'] = 'Trash Today'
            trashToday['value'] = labelNone
            trashSchedule.append(trashToday)
        else:
            for x in today_out:
                trashToday['key'] = 'today'
                trashToday['description'] = 'Trash Today'
                multiTrashToday.append(x['key'])
            trashSchedule.append(trashToday)
            trashToday['value'] = ', '.join(multiTrashToday)


        # Append Tomorrow data
        trashTomorrow = {}
        multiTrashTomorrow = []
        tomorrow_out = [x for x in trashSchedule if x['value'] == tomorrow and x['key'] not in self.defaultTrashNames]
        if len(tomorrow_out) == 0:
            trashTomorrow['key'] = 'tomorrow'
            trashTomorrow['description'] = 'Trash Tomorrow'
            trashTomorrow['value'] = labelNone
            trashSchedule.append(trashTomorrow)
        else:
            for x in tomorrow_out:
                trashTomorrow['key'] = 'tomorrow'
                trashTomorrow['description'] = 'Trash Tomorrow'
                multiTrashTomorrow.append(x['key'])
            trashSchedule.append(trashTomorrow)
            trashTomorrow['value'] = ', '.join(multiTrashTomorrow)


        # Append next pickup in days
        trashNext = {}
        next_out = [x for x in trashSchedule if x['value'] > today and x['key'] not in self.defaultTrashNames]
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
        else:
            if len(trashNext) == 0:
                trashNext['key'] = 'next'
                trashNext['value'] = (days(today, next_out[0]['value']))
                trashSchedule.append(trashNext)

        self.data = trashSchedule
