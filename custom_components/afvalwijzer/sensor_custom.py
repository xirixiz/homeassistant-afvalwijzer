from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.util import Throttle

from datetime import datetime, date
import hashlib

from .const.const import (
    _LOGGER,
    ATTR_LAST_UPDATE,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    CONF_DEFAULT_LABEL,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    MIN_TIME_BETWEEN_UPDATES,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class CustomSensor(RestoreEntity, SensorEntity):
    def __init__(self, hass, waste_type, fetch_data, config):
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data
        self.config = config
        self._id_name = config.get(CONF_ID)
        self._default_label = config.get(CONF_DEFAULT_LABEL)
        self._last_update = None
        self._days_until_collection_date = None
        self._name = (
            SENSOR_PREFIX + (f"{self._id_name} " if self._id_name else "")
        ) + waste_type
        self._state = config.get(CONF_DEFAULT_LABEL)
        self._icon = SENSOR_ICON
        self._unique_id = hashlib.sha1(
            f"{waste_type}{config.get(CONF_ID)}{config.get(CONF_POSTAL_CODE)}{config.get(CONF_STREET_NUMBER)}{config.get(CONF_SUFFIX,'')}".encode(
                "utf-8"
            )
        ).hexdigest()
        self._device_class = None

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        return self._state

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_attributes(self):
        attrs = {
            ATTR_LAST_UPDATE: self._last_update,
        }
        if isinstance(self._state, datetime):
            attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] = self._days_until_collection_date,
            attrs["device_class"] = DEVICE_CLASS_TIMESTAMP
        return attrs

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_data.update)

        waste_data_custom = self.fetch_data.waste_data_custom

        try:
            self._last_update = datetime.now().isoformat()

            if isinstance(waste_data_custom[self.waste_type], datetime):
                self._update_attributes_date(waste_data_custom[self.waste_type])
                self._device_class = DEVICE_CLASS_TIMESTAMP
            else:
                self._update_attributes_non_date(waste_data_custom[self.waste_type])
                self._device_class = None
        except ValueError:
            _LOGGER.debug("ValueError AfvalwijzerCustomSensor - unable to set value!")
            self._handle_value_error()

    def _update_attributes_date(self, collection_date):
        collection_date_object = collection_date.date()

        delta = collection_date_object - date.today()
        self._days_until_collection_date = delta.days

        self._state = collection_date_object

    def _update_attributes_non_date(self, value):
        self._state = str(value)

    def _handle_value_error(self):
        self._state = self._default_label
        self._days_until_collection_date = None
        self._last_update = datetime.now().isoformat()
