#!/usr/bin/env python3
from datetime import date, datetime, timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const.const import (
    _LOGGER,
    ATTR_LAST_UPDATE,
    ATTR_YEAR_MONTH_DAY_DATE,
    CONF_DEFAULT_LABEL,
    CONF_ID,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SENSOR_ICON,
    SENSOR_PREFIX,
)


class AfvalwijzerCustomSensor(Entity):
    def __init__(self, hass, waste_type, fetch_afvalwijzer_data, config):
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_afvalwijzer_data = fetch_afvalwijzer_data
        self.config = config

        self._id_name = self.config.get(CONF_ID)
        self._default_label = self.config.get(CONF_DEFAULT_LABEL)

        self._last_update = None
        self._name = (
            SENSOR_PREFIX
            + (self._id_name + " " if len(self._id_name) > 0 else "")
            + self.waste_type
        )
        self._state = self.config.get(CONF_DEFAULT_LABEL)
        self._icon = SENSOR_ICON
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
        if self.waste_type == "first_next_date":
            return {
                ATTR_LAST_UPDATE: self._last_update,
                ATTR_YEAR_MONTH_DAY_DATE: self._year_month_day_date,
            }
        else:
            return {ATTR_LAST_UPDATE: self._last_update}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        await self.hass.async_add_executor_job(self.fetch_afvalwijzer_data.update)

        waste_data_custom = self.fetch_afvalwijzer_data.waste_data_custom

        _LOGGER.debug(self.fetch_afvalwijzer_data.waste_data_custom)

        _LOGGER.debug(
            "Generating state via AfvalwijzerCustomSensor for = %s with value %s",
            self.waste_type,
            waste_data_custom[self.waste_type],
        )

        self._last_update = datetime.today().strftime("%d-%m-%Y %H:%M")
        self._state = waste_data_custom[self.waste_type]

        if self.waste_type == "first_next_date":
            if waste_data_custom["first_next_date"] != self._default_label:
                # Add date in different formats
                collection_date_us = datetime.strptime(
                    waste_data_custom[self.waste_type], "%d-%m-%Y"
                ).strftime("%Y-%m-%d")

                # Add attribute date in format "%Y-%m-%d"
                self._year_month_day_date = collection_date_us
