"""
@ Authors     : Bram van Dartel
@ Date        : 25/02/2019
@ Description : MijnAfvalwijzer Json/Scraper Sensor - It queries mijnafvalwijzer.nl.

sensor:
  - platform: mijnafvalwijzer
    postcode: 1111AA
    huisnummer: 1
    toevoeging: A
    label_geen: 'Geen'

23-02-2019 - Back to JSON release instead of scraper
23-02-2019 - Move scraper url, cleanup, and some minor doc fixes
24-02-2019 - Scraper debug log url fix
25-02-2019 - Update to new custom_sensor location
"""

VERSION = '3.0.4'

import logging
from datetime import date, datetime, timedelta

import bs4
import requests

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

logger = logging.getLogger(__name__)

DEFAULT_NAME = 'mijnafvalwijzer'
DOMAIN = 'mijnafvalwijzer'
ICON = 'mdi:delete-empty'
SENSOR_PREFIX = 'trash_'

CONST_POSTCODE = 'postcode'
CONST_HUISNUMMER = 'huisnummer'
CONST_TOEVOEGING = 'toevoeging'
CONST_LABEL_NONE = 'label_geen'

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
    # Setup JSON request (add sensor/devices)
    postcode = config.get(CONST_POSTCODE)
    huisnummer = config.get(CONST_HUISNUMMER)
    toevoeging = config.get(CONST_TOEVOEGING)

    if None in (postcode, huisnummer):
        logger.error("Mijnafvalwijzer - postcode or huisnummer not set!")

    url = (f"https://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode={postcode}&street=&huisnummer={huisnummer}&toevoeging={toevoeging}&platform=phone&langs=nl&")
    logger.debug(f"Json request url: {url}")
    response = requests.get(url)

    if response.status_code != requests.codes.ok:
        logger.exception("Error doing API request")
    else:
        logger.debug(f"API request ok {response.status_code}")

    json_obj = response.json()
    json_data = (json_obj['data']['ophaaldagen']['data'] + json_obj['data']['ophaaldagenNext']['data'])

    # Get unique trash shortname(s)
    uniqueTrashShortNames = []
    allTrashNames = ['firstdate', 'firstwastetype', 'today', 'tomorrow', 'next']
    uniqueTrashShortNames.extend(allTrashNames)
    sensors = []

    for item in json_data:
        element = item["nameType"]
        if element not in uniqueTrashShortNames:
            uniqueTrashShortNames.append(element)

    logger.debug(f"uniqueTrashShortNames succesfully added: {uniqueTrashShortNames}")

    data = (TrashCollectionSchedule(url, allTrashNames, config))

    for name in uniqueTrashShortNames:
        sensors.append(TrashCollectionSensor(name, data, config))
    add_devices(sensors)

    logger.debug(f"Object succesfully added as sensor(s): {sensors}")


class TrashCollectionSensor(Entity):
    """Representation of a Sensor."""
    def __init__(self, name, data, config):
        """Initialize the sensor."""
        self._name = name
        self.data = data
        self.config = config
        self._state = self.config.get(CONST_LABEL_NONE)

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
            logger.debug(f"Update called for mijnafvalwijzer item: {item}")
            if item['key'] == self._name:
                self._state = item['value']


class TrashCollectionSchedule(object):
    """Fetch new state data for the sensor."""
    def __init__(self, url, allTrashNames, config):
        """Fetch vars."""
        self._url = url
        self._allTrashNames = allTrashNames
        self.data = None
        self._config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        response = requests.get(self._url)
        json_obj = response.json()
        json_data = (json_obj['data']['ophaaldagen']['data'] + json_obj['data']['ophaaldagenNext']['data'])

        today = datetime.today().strftime('%Y-%m-%d')
        dateConvert = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=1)
        tomorrow = datetime.strftime(dateConvert, '%Y-%m-%d')

        trashType = {}
        trashNext = {}
        trashToday = {}
        trashTomorrow = {}
        multiTrashToday = []
        multiTrashTomorrow = []
        trashSchedule = []

        # Some date count functions for next
        def d(s):
            [year, month, day] = map(int, s.split('-'))
            return date(year, month, day)

        def days(start, end):
            return (d(end) - d(start)).days

        # Collect upcoming trash pickup dates for unique trash
        for name in self._allTrashNames:
            for item in json_data:
                name = item["nameType"]
                dateConvert = datetime.strptime(item['date'], '%Y-%m-%d').strftime('%d-%m-%Y')

                if name not in trashType:
                    if item['date'] >= today:
                        trash = {}
                        trashType[name] = item["nameType"]
                        trash['key'] = item['nameType']
                        trash['value'] = dateConvert
                        trashSchedule.append(trash)

                    if item['date'] > today:
                        if len(trashNext) == 0:
                            trashType[name] = "next"
                            trashNext['key'] = "next"
                            trashNext['value'] = (days(today, item['date']))
                            trashSchedule.append(trashNext)

                    if item['date'] == today:
                        trashType[name] = "today"
                        trashToday['key'] = "today"
                        trashSchedule.append(trashToday)
                        multiTrashToday.append(item['nameType'])
                        if len(multiTrashToday) != 0:
                            trashToday['value'] = ', '.join(multiTrashToday)

                    if item['date'] == tomorrow:
                        trashType[name] = "tomorrow"
                        trashTomorrow['key'] = "tomorrow"
                        trashSchedule.append(trashTomorrow)
                        multiTrashTomorrow.append(item['nameType'])
                        if len(multiTrashTomorrow) != 0:
                            trashTomorrow['value'] = ', '.join(multiTrashTomorrow)

        # Setup scraper request
        postcode = self._config.get(CONST_POSTCODE)
        huisnummer = self._config.get(CONST_HUISNUMMER)
        toevoeging = self._config.get(CONST_TOEVOEGING)
        scraper_url = (f"https://www.mijnafvalwijzer.nl/nl/{postcode}/{huisnummer}/{toevoeging}")
        logger.debug(f"Scraper request url: {scraper_url}")
        scraper_response = requests.get(scraper_url)

        if scraper_response.status_code != requests.codes.ok:
            logger.exception("Error doing scrape request")
        else:
            logger.debug(f"Scrape request ok {scraper_response.status_code}")

        scraper_data = bs4.BeautifulSoup(scraper_response.text, "html.parser")

        # Append firstDate and firstWasteType
        trashFirstDate = {}
        trashFirstDate['key'] = 'firstdate'
        trashFirstDate['value'] = scraper_data.find('p', attrs={'class':'firstDate'}).text
        trashSchedule.append(trashFirstDate)
        logger.debug(f"Data succesfully added {trashFirstDate}")

        firstWasteType = {}
        firstWasteType['key'] = 'firstwastetype'
        firstWasteType['value'] = scraper_data.find('p', attrs={'class':'firstWasteType'}).text
        trashSchedule.append(firstWasteType)
        logger.debug(f"Data succesfully added {firstWasteType}")

        # Return collected data
        logger.debug(f"trashSchedule content {trashSchedule}")

        self.data = trashSchedule
