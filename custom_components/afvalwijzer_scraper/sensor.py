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

DEFAULT_NAME = 'afvalwijzer_scraper'
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
    provider = config.get(CONST_PROVIDER)
    zipcode = config.get(CONST_ZIPCODE)
    housenumber = config.get(CONST_HOUSENUMBER)
    suffix = config.get(CONST_SUFFIX)

    if None in (zipcode, housenumber):
        _LOGGER.error("Postcode or huisnummer not set!")

    # Get unique trash shortname(s)
    sensorNames = ['firstdate', 'firstwastetype']
    sensors = []

    _LOGGER.debug("sensorNames succesfully added: %s", sensorNames)

    fetch_trash_data = (TrashSchedule(config))

    for name in sensorNames:
        sensors.append(TrashSensor(hass, name, fetch_trash_data, config))
    async_add_entities(sensors)

    _LOGGER.debug("Object succesfully added as sensor(s): %s", sensors)


class TrashSensor(Entity):
    """Representation of a Sensor."""
    def __init__(self, hass, name, fetch_trash_data, config):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._fetch_trash_data = fetch_trash_data
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

    async def async_update(self):
        """Fetch new state data for the sensor."""
        self._fetch_trash_data.update()
        self._state = self._config.get(CONST_LABEL)

        for item in self._fetch_trash_data.trash_schedule_scraper:
            _LOGGER.debug("Update called for item: %s", item)
            if item['key'] == self._name:
                self._state = item['value']


class TrashSchedule(object):
    """Fetch new state data for the sensor."""
    def __init__(self, config):
        """Fetch vars."""
        self._config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        # Setup scraper request
        provider = self._config.get(CONST_PROVIDER)
        zipcode = self._config.get(CONST_ZIPCODE)
        housenumber = self._config.get(CONST_HOUSENUMBER)
        suffix = self._config.get(CONST_SUFFIX)
        scraper_url = ("https://www.{0}/nl/{1}/{2}/{3}").format(provider, zipcode, housenumber, suffix)
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

        try:
            self.trash_schedule_scraper = trashSchedule
            _LOGGER.debug("Data trash_schedule_scraper = %s", self.trash_schedule_scraper)
        except ValueError as err:
            _LOGGER.error("Check trash_schedule_scraper %s", err.args)
            self.trash_schedule_scraper = self._config.get(CONST_LABEL)
            raise
