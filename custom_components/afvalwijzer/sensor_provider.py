#!/usr/bin/env python3
from datetime import date, datetime, timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_HIDDEN,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    ATTR_YEAR_MONTH_DAY_DATE,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class AfvalwijzerProviderSensor(Entity):
    def __init__(
        self,
        hass,
        fetch_afvalwijzer_data,
        waste_type,
        date_format,
        default_label,
        id_name,
    ):
        self.hass = hass
        self.fetch_afvalwijzer_data = fetch_afvalwijzer_data
        self.default_label = default_label
        self.date_format = date_format
        self.waste_type = waste_type
        self._name = (
            SENSOR_PREFIX + (id_name + " " if len(id_name) > 0 else "") + waste_type
        )
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
        return {
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_HIDDEN: self._hidden,
            ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date,
            ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today,
            ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow,
            ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: self._is_collection_date_day_after_tomorrow,
            ATTR_YEAR_MONTH_DAY_DATE: self._year_month_day_date,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_afvalwijzer_data.update)
        waste_data_provider = self.fetch_afvalwijzer_data.waste_data_provider
        _LOGGER.debug(
            "Generating state via AfvalwijzerProviderSensor for = %s with value %s",
            self.waste_type,
            waste_data_provider[self.waste_type],
        )

        try:
            if waste_data_provider:
                if self.waste_type in waste_data_provider:
                    # Add attribute, set the last updated status of the sensor
                    self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")

                    if waste_data_provider[self.waste_type] != self.default_label:
                        # Add date in Dutch and US format
                        collection_date_nl = waste_data_provider[self.waste_type]

                        collection_date_convert = datetime.strptime(
                            waste_data_provider[self.waste_type], "%d-%m-%Y"
                        ).strftime("%Y-%m-%d")

                        collection_date_us = datetime.strptime(
                            collection_date_convert, "%Y-%m-%d"
                        ).date()

                        collection_date_named = datetime.strptime(
                            waste_data_provider[self.waste_type], "%d-%m-%Y"
                        ).strftime("%a %d %b")

                        # Add attribute date in format "%Y-%m-%d"
                        self._year_month_day_date = str(collection_date_us)

                        # Add attribute, is the collection date today, tomorrow and/or day_after_tomorrow?
                        self._is_collection_date_today = (
                            date.today() == collection_date_us
                        )
                        self._is_collection_date_tomorrow = (
                            date.today() + timedelta(days=1) == collection_date_us
                        )
                        self._is_collection_date_day_after_tomorrow = (
                            date.today() + timedelta(days=2) == collection_date_us
                        )

                        # Add attribute, days until collection date
                        delta = collection_date_us - date.today()
                        self._days_until_collection_date = delta.days

                        self._state = collection_date_nl
                    else:
                        self._state = self.default_label
                else:
                    raise (ValueError)
            else:
                raise (ValueError)
        except ValueError:
            _LOGGER.debug("ValueError AfvalwijzerProviderSensor - unable to set value!")
            self._state = self.default_label
            self._hidden = False
            self._days_until_collection_date = None
            self._year_month_day_date = None
            self._is_collection_date_today = False
            self._is_collection_date_tomorrow = False
            self._is_collection_date_day_after_tomorrow = False
            self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")
