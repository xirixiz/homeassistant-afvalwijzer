#!/usr/bin/env python3
from datetime import date, datetime, timedelta
import hashlib

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    ATTR_YEAR_MONTH_DAY_DATE,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class ProviderSensor(RestoreEntity, SensorEntity):
    def __init__(self, hass, waste_type, fetch_data, config):
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data
        self.config = config
        self._id_name = config.get(CONF_ID)
        self._default_label = config.get(CONF_DEFAULT_LABEL)
        self._exclude_pickup_today = config.get(CONF_EXCLUDE_PICKUP_TODAY)
        self._name = SENSOR_PREFIX + (f"{self._id_name} " if self._id_name else "") + waste_type
        self._icon = SENSOR_ICON
        self._state = config.get(CONF_DEFAULT_LABEL)
        self._last_update = None
        self._days_until_collection_date = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._year_month_day_date = None
        self._unique_id = hashlib.sha1(
            f"{waste_type}{config.get(CONF_ID)}{config.get(CONF_POSTAL_CODE)}{config.get(CONF_STREET_NUMBER)}{config.get(CONF_SUFFIX,'')}".encode("utf-8")
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
        return {
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date,
            ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today,
            ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow,
            ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: self._is_collection_date_day_after_tomorrow,
            ATTR_YEAR_MONTH_DAY_DATE: self._year_month_day_date,
        }

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_data.update)
        self._update_collection_data()

    def _update_collection_data(self):
        if not self._is_valid_waste_data():
            return

        self._last_update = datetime.now().replace(microsecond=0)
        waste_data_provider = (
            self.fetch_data.waste_data_with_today
            if self._exclude_pickup_today.lower() in ("false", "no")
            else self.fetch_data.waste_data_without_today
        )

        try:
            if self.waste_type not in waste_data_provider:
                raise ValueError

            if isinstance(waste_data_provider[self.waste_type], datetime):
                self._process_datetime_data(waste_data_provider)
            else:
                self._process_non_datetime_data(waste_data_provider)

        except ValueError:
            self._handle_value_error()

    def _is_valid_waste_data(self):
        return self.fetch_data and self.waste_type

    def _process_datetime_data(self, waste_data_provider):
        _LOGGER.debug(
            f"Generating state via AfvalwijzerCustomSensor for = {self.waste_type} with value {waste_data_provider[self.waste_type].date()}"
        )

        self._year_month_day_date = waste_data_provider[self.waste_type].date()
        delta = self._year_month_day_date - date.today()
        self._days_until_collection_date = delta.days

        self._is_collection_date_today = date.today() == self._year_month_day_date
        self._is_collection_date_tomorrow = date.today() + timedelta(days=1) == self._year_month_day_date
        self._is_collection_date_day_after_tomorrow = date.today() + timedelta(days=2) == self._year_month_day_date

        self._state = datetime.strftime(self._year_month_day_date, "%d-%m-%Y")
        # self._state = waste_data_provider[self.waste_type].date()

    def _process_non_datetime_data(self, waste_data_provider):
        _LOGGER.debug(
            f"Generating state via AfvalwijzerCustomSensor for = {self.waste_type} with value {waste_data_provider[self.waste_type]}"
        )
        self._state = str(waste_data_provider[self.waste_type])

    def _handle_value_error(self):
        _LOGGER.debug("ValueError AfvalwijzerProviderSensor - unable to set value!")
        self._state = self._default_label
        self._days_until_collection_date = None
        self._year_month_day_date = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._last_update = datetime.now().replace(microsecond=0)
