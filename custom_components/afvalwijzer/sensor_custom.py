#!/usr/bin/env python3
from datetime import datetime
import hashlib

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from .const.const import (
    _LOGGER,
    ATTR_LAST_UPDATE,
    ATTR_YEAR_MONTH_DAY_DATE,
    CONF_DEFAULT_LABEL,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
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
        self._name = f"{SENSOR_PREFIX}{'{self._id_name} ' if self._id_name else ''}{self.waste_type}"
        self._state = config.get(CONF_DEFAULT_LABEL)
        self._icon = SENSOR_ICON
        self._year_month_day_date = None
        self._unique_id = hashlib.sha1(
            f"{self.waste_type}{config.get(CONF_ID)}{config.get(CONF_POSTAL_CODE)}{config.get(CONF_STREET_NUMBER)}{config.get(CONF_SUFFIX,'')}".encode(
                "utf-8"
            )
        ).hexdigest()

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
    def extra_state_attributes(self):
        attributes = {ATTR_LAST_UPDATE: self._last_update}
        if self._year_month_day_date is not None:
            attributes[ATTR_YEAR_MONTH_DAY_DATE] = self._year_month_day_date
        return attributes

    @property
    def device_class(self):
        if self._year_month_day_date == True:
            return SensorDeviceClass.TIMESTAMP

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_data.update)

        waste_data_custom = self.fetch_data.waste_data_custom

        try:
            # Add attribute, set the last updated status of the sensor
            self._last_update = datetime.now().replace(microsecond=0)

            if isinstance(waste_data_custom[self.waste_type], datetime):
                self._process_datetime_data(waste_data_custom)
            else:
                self._process_non_datetime_data(waste_data_custom)

        except ValueError:
            self._handle_value_error()

    def _process_datetime_data(self, waste_data_custom):
        _LOGGER.debug(
            f"Generating state via AfvalwijzerCustomSensor for = {self.waste_type} with value {waste_data_custom[self.waste_type].date()}"
        )
        self._year_month_day_date = waste_data_custom[self.waste_type].date()

        # date_string = datetime.strftime(self._year_month_day_date, "%d-%m-%Y")
        self._state = waste_data_custom[self.waste_type].date()

    def _process_non_datetime_data(self, waste_data_custom):
        _LOGGER.debug(
            f"Generating state via AfvalwijzerCustomSensor for = {self.waste_type} with value {waste_data_custom[self.waste_type]}"
        )
        self._state = str(waste_data_custom[self.waste_type])

    def _handle_value_error(self):
        _LOGGER.debug("ValueError AfvalwijzerCustomSensor - unable to set value!")
        self._state = self._default_label
        self._year_month_day_date = None
        self._last_update = datetime.now().replace(microsecond=0)
