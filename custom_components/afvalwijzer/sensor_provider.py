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
    CONF_DEFAULT_LABEL,
    CONF_ID,
    CONF_INCLUDE_DATE_TODAY,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class AfvalwijzerProviderSensor(Entity):
    def __init__(self, hass, waste_type, fetch_afvalwijzer_data, config):
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_afvalwijzer_data = fetch_afvalwijzer_data
        self.config = config

        self._id_name = self.config.get(CONF_ID)
        self._default_label = self.config.get(CONF_DEFAULT_LABEL)
        self._include_date_today = self.config.get(CONF_INCLUDE_DATE_TODAY)

        self._name = (
            SENSOR_PREFIX
            + (self._id_name + " " if len(self._id_name) > 0 else "")
            + self.waste_type
        )
        self._icon = SENSOR_ICON
        self._hidden = False
        self._state = self.config.get(CONF_DEFAULT_LABEL)
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

        if self._include_date_today.casefold() in ("true", "yes"):
            waste_data_provider = self.fetch_afvalwijzer_data.waste_data_with_today
        else:
            waste_data_provider = self.fetch_afvalwijzer_data.waste_data_without_today

        try:
            if waste_data_provider:
                if self.waste_type in waste_data_provider:
                    # Add attribute, set the last updated status of the sensor
                    self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")

                    if isinstance(waste_data_provider[self.waste_type], datetime):
                        _LOGGER.debug(
                            "Generating state via AfvalwijzerCustomSensor for = %s with value %s",
                            self.waste_type,
                            waste_data_provider[self.waste_type].date(),
                        )
                        # Add the US date format
                        collection_date_us = waste_data_provider[self.waste_type].date()
                        self._year_month_day_date = str(collection_date_us)

                        # Add the days until the collection date
                        delta = collection_date_us - date.today()
                        self._days_until_collection_date = delta.days

                        # Check if the collection days are in today, tomorrow and/or the day after tomorrow
                        self._is_collection_date_today = (
                            date.today() == collection_date_us
                        )
                        self._is_collection_date_tomorrow = (
                            date.today() + timedelta(days=1) == collection_date_us
                        )
                        self._is_collection_date_day_after_tomorrow = (
                            date.today() + timedelta(days=2) == collection_date_us
                        )

                        # Add the NL date format as default state
                        self._state = datetime.strftime(
                            waste_data_provider[self.waste_type].date(), "%d-%m-%Y"
                        )
                    else:
                        _LOGGER.debug(
                            "Generating state via AfvalwijzerCustomSensor for = %s with value %s",
                            self.waste_type,
                            waste_data_provider[self.waste_type],
                        )
                        # Add non-date as default state
                        self._state = str(waste_data_provider[self.waste_type])
                else:
                    raise (ValueError)
            else:
                raise (ValueError)
        except ValueError:
            _LOGGER.debug("ValueError AfvalwijzerProviderSensor - unable to set value!")
            self._state = self._default_label
            self._hidden = False
            self._days_until_collection_date = None
            self._year_month_day_date = None
            self._is_collection_date_today = False
            self._is_collection_date_tomorrow = False
            self._is_collection_date_day_after_tomorrow = False
            self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")
