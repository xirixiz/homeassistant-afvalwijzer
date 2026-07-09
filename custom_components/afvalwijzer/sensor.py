"""Afvalwijzer integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const.const import (
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    DOMAIN,
)
from .sensor_custom import CustomSensor
from .sensor_provider import ProviderSensor

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COLLECTOR, default="mijnafvalwijzer"): cv.string,
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_STREET_NAME, default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
        vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
        vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME, default=""): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities,
    discovery_info=None,
) -> None:
    """Set up sensors via YAML or discovery (legacy)."""
    _LOGGER.warning(
        "Configuration of the Afvalwijzer integration in YAML is deprecated "
        "and will be removed in a future release; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensors from a config entry (config flow)."""
    config: dict[str, Any] = {**entry.data, **entry.options}
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    await _setup_sensors(hass, config, async_add_entities, coordinator)


async def _setup_sensors(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities,
    coordinator: Any,
) -> None:
    """General setup logic for platform and config entry."""
    _LOGGER.debug(
        "Setting up Afvalwijzer sensors for provider: %s.",
        config.get(CONF_COLLECTOR),
    )

    waste_data_with_today = coordinator.waste_data_with_today or {}
    waste_data_custom = coordinator.waste_data_custom or {}

    entities: list[Any] = [
        ProviderSensor(hass, wtype, coordinator, config) for wtype in waste_data_with_today
    ]
    entities.extend(
        CustomSensor(hass, wtype, coordinator, config) for wtype in waste_data_custom
    )

    if coordinator.notification_data:
        entities.append(ProviderSensor(hass, "notifications", coordinator, config))
        _LOGGER.debug("Added notification sensor for provider")

    if not entities:
        _LOGGER.error("No entities created; check configuration or collector output.")
        return

    _LOGGER.info("Adding %d sensors for Afvalwijzer.", len(entities))
    async_add_entities(entities, True)



