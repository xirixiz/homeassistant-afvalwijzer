from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .const.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

try:
    from homeassistant.const import Platform
    from homeassistant.helpers import config_validation as cv

    PLATFORMS: list[Platform] = [Platform.SENSOR]
    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

except ModuleNotFoundError:
    PLATFORMS = []
    CONFIG_SCHEMA = None


def _skip_runtime_setup() -> bool:
    return os.getenv("AFVALWIJZER_SKIP_INIT") == "1"


async def async_setup(hass: "HomeAssistant", config: "ConfigType") -> bool:
    if _skip_runtime_setup():
        return True

    if PLATFORMS:
        hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    if _skip_runtime_setup():
        return True

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    if _skip_runtime_setup():
        return True

    if not PLATFORMS:
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
