#!/usr/bin/env python3
from datetime import datetime, date, timedelta
import hashlib

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    ATTR_YEAR_MONTH_DAY_DATE,
    ATTR_ISOFORMATTED_DATE,
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


class ProviderSensor(Entity):
    def __init__(self, hass, waste_type, fetch_data, config):
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data
        self.config = config
        self._id_name = config.get(CONF_ID)
        self._default_label = config.get(CONF_DEFAULT_LABEL)
        self._exclude_pickup_today = config.get(CONF_EXCLUDE_PICKUP_TODAY)
        self._name = (
            SENSOR_PREFIX + (f"{self._id_name} " if self._id_name else "")
        ) + waste_type
        self._icon = SENSOR_ICON
        self._state = config.get(CONF_DEFAULT_LABEL)
        self._last_update = None
        self._days_until_collection_date = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._year_month_day_date = None
        self._isoformatted_date = None
        self._unique_id = hashlib.sha1(
            f"{waste_type}{config.get(CONF_ID)}{config.get(CONF_POSTAL_CODE)}{config.get(CONF_STREET_NUMBER)}{config.get(CONF_SUFFIX,'')}".encode(
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
        return {
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date,
            ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today,
            ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow,
            ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: self._is_collection_date_day_after_tomorrow,
            ATTR_YEAR_MONTH_DAY_DATE: self._year_month_day_date,
            ATTR_ISOFORMATTED_DATE: self._isoformatted_date,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_data.update)

        waste_data_provider = (
            self.fetch_data.waste_data_with_today
            if self._exclude_pickup_today.casefold() in ("false", "no")
            else self.fetch_data.waste_data_without_today
        )

        try:
            if not waste_data_provider or self.waste_type not in waste_data_provider:
                raise ValueError
            self._last_update = datetime.now().strftime("%d-%m-%Y %H:%M")

            if isinstance(waste_data_provider[self.waste_type], datetime):
                self._update_attributes_date(waste_data_provider[self.waste_type])
            else:
                self._update_attributes_non_date(waste_data_provider[self.waste_type])
        except ValueError:
            self._handle_value_error()

    def _update_attributes_date(self, collection_date):
        self._isoformatted_date = datetime.isoformat(collection_date)

        collection_date_us = collection_date.date()
        self._year_month_day_date = str(collection_date_us)

        delta = collection_date_us - date.today()
        self._days_until_collection_date = delta.days

        self._update_collection_date_flags(collection_date_us)

        self._state = datetime.strftime(collection_date_us, "%d-%m-%Y")

    def _update_attributes_non_date(self, value):
        self._state = str(value)

    def _update_collection_date_flags(self, collection_date_us):
        today = date.today()
        self._is_collection_date_today = collection_date_us == today
        self._is_collection_date_tomorrow = collection_date_us == today + timedelta(days=1)
        self._is_collection_date_day_after_tomorrow = collection_date_us == today + timedelta(days=2)
