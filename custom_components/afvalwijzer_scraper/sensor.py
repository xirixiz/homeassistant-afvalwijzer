"""
@ Authors     : Bram van Dartel
@ Description : Afvalwijzer Json/Scraper Sensor - It queries mijnafvalwijzer.nl or afvalstoffendienstkalender.nl.
"""

VERSION = '1.0.0'

import logging
import bs4

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

SCAN_INTERVAL = timedelta(seconds=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3600)
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
    # Setup JSON request (add sensor/devices)
    provider = config.get(CONST_PRO)
    postcode = config.get(CONST_POSTCODE)
    huisnummer = config.get(CONST_HUISNUMMER)
    toevoeging = config.get(CONST_TOEVOEGING)

    if None in (postcode, huisnummer):
        _LOGGER.error("Postcode or huisnummer not set!")

    # Get unique trash shortname(s)
    sensorNames = ['firstdate', 'firstwastetype']
    sensors = []

    _LOGGER.debug("sensorNames succesfully added: %s", sensorNames)

    data = (TrashCollectionSchedule(url, config))

    for name in sensorNames:
        sensors.append(TrashCollectionSensor(name, data, config))
    async_add_entities(sensors)

    _LOGGER.debug("Object succesfully added as sensor(s): %s", sensors)


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

    async def async_update(self):
        """Fetch new state data for the sensor."""
        self.data.update()
        self._state = self.config.get(CONST_LABEL_NONE)

        for item in self.data.data:
            _LOGGER.debug("Update called for item: %s", item)
            if item['key'] == self._name:
                self._state = item['value']


class TrashCollectionSchedule(object):
    """Fetch new state data for the sensor."""
    def __init__(self, url, allTrashNames, config):
        """Fetch vars."""
        self._url = url
        self.data = None
        self._config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""

        # Setup scraper request
        url = self._config.get(CONST_URL)
        provider = config.get(CONST_PROVIDER)
        zipcode = config.get(CONST_ZIPCODE)
        housenumber = config.get(CONST_HOUSENUMBER)
        suffix = config.get(CONST_SUFFIX)
        count_today = config.get(CONST_COUNT_TODAY)        
        scraper_url = ("https://www.{0}/nl/{1}/{2}/{3}").format(url, postcode, huisnummer, toevoeging)
        scraper_response = requests.get(scraper_url)
        trashSchedule = []

        if scraper_response.status_code != requests.codes.ok:
            _LOGGER.exception("Error doing scrape request")
        else:
            _LOGGER.debug("Scrape request ok %s", scraper_response.status_code)

        scraper_data = bs4.BeautifulSoup(scraper_response.text, "html.parser")

        # Append firstDate and firstWasteType
        trashFirstDate = {}
        trashFirstDate['key'] = 'firstdate'
        trashFirstDate['value'] = scraper_data.find('p', attrs={'class':'firstDate'}).text
        trashSchedule.append(trashFirstDate)
        _LOGGER.debug("Data succesfully added %s", trashFirstDate)

        firstWasteType = {}
        firstWasteType['key'] = 'firstwastetype'
        firstWasteType['value'] = scraper_data.find('p', attrs={'class':'firstWasteType'}).text
        trashSchedule.append(firstWasteType)
        _LOGGER.debug("Data succesfully added %s", firstWasteType)

        # Return collected data
        _LOGGER.debug("trashSchedule content %s", trashSchedule)

        self.data = trashSchedule
