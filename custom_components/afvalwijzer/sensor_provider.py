#!/usr/bin/env python3
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity
from datetime import datetime, date, timedelta
import hashlib

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    CONF_DATE_ISOFORMAT,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class ProviderSensor(RestoreEntity, SensorEntity):
    """Representation of a provider-based waste sensor."""

    def __init__(self, hass, waste_type, fetch_data, config):
        """Initialize the sensor."""
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data  # This should be an instance of AfvalwijzerData
        self.config = config
        self._id_name = config.get(CONF_ID)
        self._default_label = config.get(CONF_DEFAULT_LABEL)
        self._exclude_pickup_today = str(
            config.get(CONF_EXCLUDE_PICKUP_TODAY)).lower()
        self._name = (
            SENSOR_PREFIX + (f"{self._id_name} " if self._id_name else "")
        ) + waste_type
        self._last_update = None
        self._days_until_collection_date = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._date_isoformat = str(config.get(CONF_DATE_ISOFORMAT)).lower()
        self._state = self._default_label
        self._icon = SENSOR_ICON
        self._unique_id = hashlib.sha1(
            f"{waste_type}{config.get(CONF_ID)}{config.get(CONF_POSTAL_CODE)}{config.get(CONF_STREET_NUMBER)}{config.get(CONF_SUFFIX, '')}".encode(
                "utf-8"
            )
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
        return {
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date,
            ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today,
            ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow,
            ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: self._is_collection_date_day_after_tomorrow,
        }

    async def async_update(self):
        """Fetch the latest data and update the state."""
        _LOGGER.debug(f"Updating sensor: {self.name}")

        try:
            # Call update method from fetch_data
            await self.hass.async_add_executor_job(self.fetch_data.update)

            # Select the correct waste data based on exclude_pickup_today
            waste_data_provider = (
                self.fetch_data.waste_data_with_today
                if self._exclude_pickup_today in ("false", "no")
                else self.fetch_data.waste_data_without_today
            )

            if not waste_data_provider or self.waste_type not in waste_data_provider:
                raise ValueError(f"No data for waste type: {self.waste_type}")

            # Update attributes and state based on the waste data
            collection_date = waste_data_provider[self.waste_type]
            if isinstance(collection_date, datetime):
                self._update_attributes_date(collection_date)
            else:
                self._update_attributes_non_date(collection_date)

        except Exception as err:
            _LOGGER.error(f"Error updating sensor {self.name}: {err}")
            self._handle_value_error()

    def _update_attributes_date(self, collection_date):
        """Update attributes for a datetime value."""
        collection_date_object = (
            collection_date.isoformat() if self._date_isoformat in (
                "true", "yes") else collection_date.date()
        )
        collection_date_delta = collection_date.date()
        delta = collection_date_delta - date.today()

        self._days_until_collection_date = delta.days
        self._update_collection_date_flags(collection_date_delta)
        self._device_class = SensorDeviceClass.TIMESTAMP
        self._state = collection_date_object

    def _update_attributes_non_date(self, value):
        """Update attributes for a non-datetime value."""
        self._state = str(value)
        self._days_until_collection_date = None
        self._device_class = None

    def _update_collection_date_flags(self, collection_date_delta):
        """Update flags for collection date."""
        today = date.today()
        self._is_collection_date_today = collection_date_delta == today
        self._is_collection_date_tomorrow = collection_date_delta == today + \
            timedelta(days=1)
        self._is_collection_date_day_after_tomorrow = collection_date_delta == today + \
            timedelta(days=2)

    def _handle_value_error(self):
        """Handle errors in fetching data."""
        self._state = self._default_label
        self._is_collection_date_today = None
        self._is_collection_date_tomorrow = None
        self._is_collection_date_day_after_tomorrow = None
        self._days_until_collection_date = None
        self._device_class = None
        self._last_update = datetime.now().isoformat()
