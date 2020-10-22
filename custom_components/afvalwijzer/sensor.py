#!/usr/bin/env python3
"""
Sensor component for Afvalwijzer
Author: Bram van Dartel - xirixiz
Special thanks to: https://github.com/heyajohnny/afvalinfo for allowing me to copy code for the scraper functionality!
"""

import asyncio
import re
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
    CONF_API_TOKEN,
    CONF_DATE_FORMAT,
    CONF_DEFAULT_LABEL,
    CONF_ID,
    CONF_INCLUDE_DATE_TODAY,
    CONF_POSTAL_CODE,
    CONF_PROVIDER,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
)
from .provider.afvalwijzer import AfvalWijzer
from .sensor_custom import AfvalwijzerCustomSensor
from .sensor_provider import AfvalwijzerProviderSensor

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_PROVIDER, default="mijnafvalwijzer"): cv.string,
        vol.Optional(CONF_API_TOKEN, default=""): cv.string,
        vol.Required(CONF_POSTAL_CODE, default="1111AA"): cv.string,
        vol.Required(CONF_STREET_NUMBER, default="1"): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_DATE_FORMAT, default="%d-%m-%Y"): cv.string,
        vol.Optional(CONF_INCLUDE_DATE_TODAY, default="false"): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL, default="Geen"): cv.string,
        vol.Optional(CONF_ID, default=""): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.debug("Setup Afvalwijzer sensor")

    provider = config.get(CONF_PROVIDER).lower().strip()
    api_token = config.get(CONF_API_TOKEN).strip()
    postal_code = config.get(CONF_POSTAL_CODE).strip()
    street_number = config.get(CONF_STREET_NUMBER).strip()
    suffix = config.get(CONF_SUFFIX).upper().strip()
    date_format = config.get(CONF_DATE_FORMAT).strip()
    include_date_today = config.get(CONF_INCLUDE_DATE_TODAY).strip()
    default_label = config.get(CONF_DEFAULT_LABEL).strip()
    id_name = config.get(CONF_ID).strip()

    _LOGGER.debug("Afvalwijzer provider = %s", provider)
    _LOGGER.debug("Afvalwijzer zipcode = %s", postal_code)
    _LOGGER.debug("Afvalwijzer street_number = %s", street_number)

    try:
        afvalwijzer = await hass.async_add_executor_job(
            partial(
                AfvalWijzer,
                provider,
                api_token,
                postal_code,
                street_number,
                suffix,
                include_date_today,
                default_label,
            )
        )
    except ValueError as err:
        _LOGGER.error("Check afvalwijzer platform settings %s", err.args)
        raise
    fetch_afvalwijzer_data = AfvalwijzerData(
        provider,
        api_token,
        postal_code,
        street_number,
        suffix,
        include_date_today,
        default_label,
    )

    waste_types_provider = afvalwijzer.waste_types_provider
    _LOGGER.debug("Generating waste_types_provider list = %s", waste_types_provider)
    waste_types_custom = afvalwijzer.waste_types_custom
    _LOGGER.debug("Generating waste_types_custom list = %s", waste_types_custom)
    # waste_data = {**waste_data_provider, **waste_data_custom}

    entities = []

    for waste_type in waste_types_provider:
        _LOGGER.debug("Adding sensor provider: %s", waste_type)
        entities.append(
            AfvalwijzerProviderSensor(
                hass,
                fetch_afvalwijzer_data,
                waste_type,
                date_format,
                default_label,
                id_name,
            )
        )
    for waste_type in waste_types_custom:
        _LOGGER.debug("Adding sensor custom: %s", waste_type)
        entities.append(
            AfvalwijzerCustomSensor(
                hass, fetch_afvalwijzer_data, waste_type, default_label, id_name
            )
        )
    _LOGGER.debug("Entities appended = %s", entities)
    async_add_entities(entities)


class AfvalwijzerData(object):
    def __init__(
        self,
        provider,
        api_token,
        postal_code,
        street_number,
        suffix,
        include_date_today,
        default_label,
    ):
        self.fetch_afvalwijzer_data = None
        self.provider = provider
        self.api_token = api_token
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.include_date_today = include_date_today
        self.default_label = default_label

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        try:
            afvalwijzer = AfvalWijzer(
                self.provider,
                self.api_token,
                self.postal_code,
                self.street_number,
                self.suffix,
                self.include_date_today,
                self.default_label,
            )
        except ValueError as err:
            _LOGGER.error("Check afvalwijzer platform settings %s", err.args)
            raise
        try:
            self.waste_data_provider = afvalwijzer.waste_data_provider
            _LOGGER.debug(
                "Generating waste_data_provider = %s", self.waste_data_provider
            )
        except ValueError as err:
            _LOGGER.error("Check waste_data_provider %s", err.args)
            self.waste_data_provider = self.default_label
            raise
        try:
            self.waste_data_custom = afvalwijzer.waste_data_custom
            _LOGGER.debug("Generating waste_data_custom = %s", self.waste_data_custom)
        except ValueError as err:
            _LOGGER.error("Check waste_data_custom %s", err.args)
            self.waste_data_custom = self.default_label
            raise
