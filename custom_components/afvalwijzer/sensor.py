#!/usr/bin/env python3
"""
Sensor component Afvalwijzer
Author: Bram van Dartel - xirixiz
"""

from functools import partial

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import voluptuous as vol

from .collector.mijnafvalwijzer import MijnAfvalWijzerCollector
from .collector.ximmio import XimmioCollector
from .const.const import (
    _LOGGER,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    MIN_TIME_BETWEEN_UPDATES,
    PARALLEL_UPDATES,
    SCAN_INTERVAL,
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_XIMMIO,
    STARTUP_MESSAGE,
)
from .sensor_custom import CustomSensor
from .sensor_provider import ProviderSensor

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_COLLECTOR.strip().lower(), default="mijnafvalwijzer"
        ): cv.string,
        vol.Required(CONF_POSTAL_CODE.strip(), default="1234AB"): cv.string,
        vol.Required(CONF_STREET_NUMBER.strip(), default="5"): cv.string,
        vol.Optional(CONF_SUFFIX.strip(), default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY.strip(), default="false"): cv.string,
        vol.Optional(CONF_EXCLUDE_LIST.strip().lower(), default=""): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL.strip(), default="Geen"): cv.string,
        vol.Optional(CONF_ID.strip().lower(), default=""): cv.string,
    }
)

_LOGGER.info(STARTUP_MESSAGE)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    provider = config.get(CONF_COLLECTOR)
    postal_code = config.get(CONF_POSTAL_CODE)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX)
    exclude_pickup_today = config.get(CONF_EXCLUDE_PICKUP_TODAY)
    exclude_list = config.get(CONF_EXCLUDE_LIST)
    default_label = config.get(CONF_DEFAULT_LABEL)

    _LOGGER.debug("Afvalwijzer provider = %s", provider)
    _LOGGER.debug("Afvalwijzer zipcode = %s", postal_code)
    _LOGGER.debug("Afvalwijzer street_number = %s", street_number)

    try:
        if provider in SENSOR_COLLECTORS_AFVALWIJZER:
            collector = await hass.async_add_executor_job(
                partial(
                    MijnAfvalWijzerCollector,
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            )
        elif provider in SENSOR_COLLECTORS_XIMMIO.keys():
            collector = await hass.async_add_executor_job(
                partial(
                    XimmioCollector,
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            )
    except ValueError as err:
        _LOGGER.error("Check afvalwijzer platform settings %s", err.args)

    if collector == "":
        raise ValueError("Invalid provider: %s, please verify", provider)

    fetch_data = AfvalwijzerData(config)

    waste_types_provider = collector.waste_types_provider
    _LOGGER.debug("Generating waste_types_provider list = %s", waste_types_provider)
    waste_types_custom = collector.waste_types_custom
    _LOGGER.debug("Generating waste_types_custom list = %s", waste_types_custom)

    entities = list()

    for waste_type in waste_types_provider:
        _LOGGER.debug("Adding sensor provider: %s", waste_type)
        entities.append(ProviderSensor(hass, waste_type, fetch_data, config))
    for waste_type in waste_types_custom:
        _LOGGER.debug("Adding sensor custom: %s", waste_type)
        entities.append(CustomSensor(hass, waste_type, fetch_data, config))

    _LOGGER.debug("Entities appended = %s", entities)
    async_add_entities(entities)


class AfvalwijzerData(object):
    def __init__(self, config):
        self.config = config

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        provider = self.config.get(CONF_COLLECTOR)
        postal_code = self.config.get(CONF_POSTAL_CODE)
        street_number = self.config.get(CONF_STREET_NUMBER)
        suffix = self.config.get(CONF_SUFFIX)
        exclude_pickup_today = self.config.get(CONF_EXCLUDE_PICKUP_TODAY)
        default_label = self.config.get(CONF_DEFAULT_LABEL)
        exclude_list = self.config.get(CONF_EXCLUDE_LIST)

        try:
            if provider in SENSOR_COLLECTORS_AFVALWIJZER:
                collector = MijnAfvalWijzerCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            elif provider in SENSOR_COLLECTORS_XIMMIO.keys():
                collector = XimmioCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
        except ValueError as err:
            _LOGGER.error("Check afvalwijzer platform settings %s", err.args)

        # waste data provider update - with today
        try:
            self.waste_data_with_today = collector.waste_data_with_today
        except ValueError as err:
            _LOGGER.error("Check waste_data_provider %s", err.args)
            self.waste_data_with_today = default_label

        # waste data provider update - without today
        try:
            self.waste_data_without_today = collector.waste_data_without_today
        except ValueError as err:
            _LOGGER.error("Check waste_data_provider %s", err.args)
            self.waste_data_without_today = default_label

        # waste data custom update
        try:
            self.waste_data_custom = collector.waste_data_custom
        except ValueError as err:
            _LOGGER.error("Check waste_data_custom %s", err.args)
            self.waste_data_custom = default_label
