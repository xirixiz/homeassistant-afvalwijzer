"""Afvalwijzer integration."""

from datetime import datetime
import hashlib

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class CustomSensor(RestoreEntity, SensorEntity):
    """Representation of a custom-based waste sensor."""

    def __init__(self, hass, waste_type, fetch_data, config):
        """Initialize the sensor."""
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data
        self.config = config
        self._id_name = config.get(CONF_ID)
        self._default_label = config.get(CONF_DEFAULT_LABEL)
        self._date_isoformat = str(config.get(CONF_DATE_ISOFORMAT)).lower()
        self._last_update = None
        self._days_until_collection_date = None
        self._name = (
            SENSOR_PREFIX + (f"{self._id_name} " if self._id_name else "")
        ) + waste_type
        self._state = self._default_label
        self._icon = SENSOR_ICON
        self._unique_id = hashlib.sha1(
            f"{waste_type}{config.get(CONF_ID)}{config.get(CONF_COLLECTOR)}{config.get(CONF_POSTAL_CODE)}{config.get(CONF_STREET_NUMBER)}{config.get(CONF_SUFFIX, '')}".encode()
        ).hexdigest()
        self._device_class = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state_attributes(self):
        """Return the attributes of the sensor."""
        attrs = {
            ATTR_LAST_UPDATE: self._last_update,
        }
        if "next_date" in self.name.lower():
            attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] = self._days_until_collection_date
        if isinstance(self._state, datetime):
            attrs["device_class"] = self._device_class
        return attrs

    async def async_update(self):
        """Fetch the latest data and update the state."""
        _LOGGER.debug(f"Updating custom sensor: {self.name}")

        try:
            # Call update method from fetch_data
            await self.hass.async_add_executor_job(self.fetch_data.update)

            # Get waste data for custom sensors
            waste_data_custom = self.fetch_data.waste_data_custom

            if not waste_data_custom or self.waste_type not in waste_data_custom:
                raise ValueError(f"No data for waste type: {self.waste_type}")

            # Update attributes and state based on waste data
            collection_date = waste_data_custom[self.waste_type]
            if isinstance(collection_date, datetime):
                self._update_attributes_date(collection_date)
            else:
                self._update_attributes_non_date(collection_date)

            # Update last_update timestamp
            self._last_update = dt_util.now().isoformat()

        except Exception as err:
            _LOGGER.error(f"Error updating custom sensor {self.name}: {err}")
            self._handle_value_error()

    def _update_attributes_date(self, collection_date):
        """Update attributes for a datetime value."""
        collection_date_object = (
            collection_date.isoformat()
            if self._date_isoformat in ("true", "yes")
            else collection_date.date()
        )
        collection_date_delta = collection_date.date()
        delta = collection_date_delta - dt_util.now().date()

        self._days_until_collection_date = delta.days
        self._device_class = SensorDeviceClass.TIMESTAMP
        self._state = collection_date_object

    def _update_attributes_non_date(self, value):
        """Update attributes for a non-datetime value."""
        self._state = str(value)
        self._days_until_collection_date = None
        self._device_class = None

    def _handle_value_error(self):
        """Handle errors in fetching data."""
        self._state = self._default_label
        self._days_until_collection_date = None
        self._device_class = None
        self._last_update = dt_util.now().isoformat()
