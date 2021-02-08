#!/usr/bin/env python3
"""
Sensor component Afvalwijzer
Author: Bram van Dartel - xirixiz
"""

from datetime import date, datetime, timedelta
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from requests.exceptions import HTTPError

from .const.const import (
    _LOGGER,
    CONF_DEFAULT_LABEL,
    CONF_ID,
    CONF_INCLUDE_DATE_TODAY,
    CONF_POSTAL_CODE,
    CONF_PROVIDER,
    CONF_STREET_NUMBER,
    CONF_EXCLUDE_LIST,
    CONF_SUFFIX,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SCAN_INTERVAL,
    STARTUP_MESSAGE,
)
from .provider.afvalwijzer import AfvalWijzer
from .sensor_custom import AfvalwijzerCustomSensor
from .sensor_provider import AfvalwijzerProviderSensor

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_PROVIDER.strip().lower(), default="mijnafvalwijzer"
        ): cv.string,
        vol.Required(CONF_POSTAL_CODE.strip(), default="1234AB"): cv.string,
        vol.Required(CONF_STREET_NUMBER.strip(), default="5"): cv.string,
        vol.Optional(CONF_SUFFIX.strip(), default=""): cv.string,
        vol.Optional(CONF_INCLUDE_DATE_TODAY.strip(), default="false"): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL.strip(), default="Geen"): cv.string,
        vol.Optional(CONF_ID.strip().lower(), default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_LIST.strip().lower(), default=""): cv.string,
    }
)

_LOGGER.info(STARTUP_MESSAGE)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    provider = config.get(CONF_PROVIDER)
    postal_code = config.get(CONF_POSTAL_CODE)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX)
    include_date_today = config.get(CONF_INCLUDE_DATE_TODAY)
    default_label = config.get(CONF_DEFAULT_LABEL)
    exclude_list = config.get(CONF_EXCLUDE_LIST)

    _LOGGER.debug("Afvalwijzer provider = %s", provider)
    _LOGGER.debug("Afvalwijzer zipcode = %s", postal_code)
    _LOGGER.debug("Afvalwijzer street_number = %s", street_number)

    try:
        afvalwijzer = await hass.async_add_executor_job(
            partial(
                AfvalWijzer,
                provider,
                postal_code,
                street_number,
                suffix,
                include_date_today,
                default_label,
                exclude_list,
            )
        )
    except ValueError as err:
        _LOGGER.error("Check afvalwijzer platform settings %s", err.args)
        raise

    fetch_afvalwijzer_data = AfvalwijzerData(config)

    waste_types_provider = afvalwijzer.waste_types_provider
    _LOGGER.debug("Generating waste_types_provider list = %s", waste_types_provider)
    waste_types_custom = afvalwijzer.waste_types_custom
    _LOGGER.debug("Generating waste_types_custom list = %s", waste_types_custom)

    entities = []

    for waste_type in waste_types_provider:
        _LOGGER.debug("Adding sensor provider: %s", waste_type)
        entities.append(
            AfvalwijzerProviderSensor(hass, waste_type, fetch_afvalwijzer_data, config)
        )
    for waste_type in waste_types_custom:
        _LOGGER.debug("Adding sensor custom: %s", waste_type)
        entities.append(
            AfvalwijzerCustomSensor(hass, waste_type, fetch_afvalwijzer_data, config)
        )

    _LOGGER.debug("Entities appended = %s", entities)
    async_add_entities(entities)


class AfvalwijzerData(object):
    def __init__(self, config):
        self.config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        provider = self.config.get(CONF_PROVIDER)
        postal_code = self.config.get(CONF_POSTAL_CODE)
        street_number = self.config.get(CONF_STREET_NUMBER)
        suffix = self.config.get(CONF_SUFFIX)
        include_date_today = self.config.get(CONF_INCLUDE_DATE_TODAY)
        default_label = self.config.get(CONF_DEFAULT_LABEL)
        exclude_list = self.config.get(CONF_EXCLUDE_LIST)

        try:
            afvalwijzer = AfvalWijzer(
                provider,
                postal_code,
                street_number,
                suffix,
                include_date_today,
                default_label,
                exclude_list,
            )
        except ValueError as err:
            _LOGGER.error("Check afvalwijzer platform settings %s", err.args)
            raise

        # waste data provider update - with today
        try:
            self.waste_data_with_today = afvalwijzer.waste_data_with_today
        except ValueError as err:
            _LOGGER.error("Check waste_data_provider %s", err.args)
            self.waste_data_with_today = self._default_label
            raise

        # waste data provider update - without today
        try:
            self.waste_data_without_today = afvalwijzer.waste_data_without_today
        except ValueError as err:
            _LOGGER.error("Check waste_data_provider %s", err.args)
            self.waste_data_without_today = self._default_label
            raise

        # waste data custom update
        try:
            self.waste_data_custom = afvalwijzer.waste_data_custom
        except ValueError as err:
            _LOGGER.error("Check waste_data_custom %s", err.args)
            self.waste_data_custom = self._default_label
            raise
