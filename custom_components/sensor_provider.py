#!/usr/bin/env python3
from datetime import datetime, date, timedelta
from .const.const import (
    _LOGGER,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SENSOR_ICON,
    SENSOR_PREFIX,
    ATTR_LAST_UPDATE,
    ATTR_HIDDEN,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_YEAR_MONTH_DAY_DATE
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


class AfvalwijzerProviderSensor(Entity):
    def __init__(self, hass, fetch_afvalwijzer_data, waste_type, date_format, default_label):
        self.hass = hass
        self.fetch_afvalwijzer_data = fetch_afvalwijzer_data
        self.default_label = default_label
        self.date_format = date_format
        self.waste_type = waste_type
        self._name = SENSOR_PREFIX + waste_type
        self._icon = SENSOR_ICON
        self._hidden = False
        self._state = None
        self._last_update = None
        self._days_until_collection_date = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._year_month_day_date = None

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        return {ATTR_YEAR_MONTH_DAY_DATE: self._year_month_day_date, ATTR_LAST_UPDATE: self._last_update, ATTR_HIDDEN: self._hidden, ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date, ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today, ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow, ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: self._is_collection_date_day_after_tomorrow}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_afvalwijzer_data.update)
        waste_data_provider = self.fetch_afvalwijzer_data.waste_data_provider
        _LOGGER.debug("Generating state via AfvalwijzerProviderSensor for = %s", waste_data_provider)

        try:
            if waste_data_provider:
                if self.waste_type in waste_data_provider:
                    if waste_data_provider[self.waste_type] != self.default_label:

                        # Add date in Dutch and US format
                        collection_date_nl = waste_data_provider[self.waste_type]
                        _LOGGER.debug("collection_date_nl = %s", collection_date_nl)
                        collection_date_convert_to_us = datetime.strptime(waste_data_provider[self.waste_type], "%d-%m-%Y").strftime("%Y-%m-%d")
                        collection_date_us = datetime.strptime(collection_date_convert_to_us, "%Y-%m-%d").date()
                        _LOGGER.debug("collection_date_us = %s", collection_date_us)

                        # Add attribute date in format "%Y-%m-%d"
                        self._year_month_day_date = str(collection_date_us)

                        # Add attribute, set the last updated status of the sensor
                        self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")

                        # Add attribute, is the collection date today, tomorrow and/or day_after_tomorrow?
                        self._is_collection_date_today = date.today() == collection_date_us
                        self._is_collection_date_tomorrow = date.today() + timedelta(days=1) == collection_date_us
                        self._is_collection_date_day_after_tomorrow = date.today() + timedelta(days=2) == collection_date_us

                        # Add attribute, days until collection date
                        delta = collection_date_us - date.today()
                        self._days_until_collection_date = delta.days
                        self._state = collection_date_nl
                    else:
                        raise (ValueError)
                else:
                    raise (ValueError)
            else:
                raise (ValueError)
        except ValueError:
            _LOGGER.debug("ValueError AfvalwijzerProviderSensor")
            self._state = self.default_label
            self._hidden = False
            self._days_until_collection_date = None
            self._year_month_day_date = None
            self._is_collection_date_today = False
            self._is_collection_date_tomorrow = False
            self._is_collection_date_day_after_tomorrow = False
            self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")