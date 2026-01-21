"""Afvalwijzer integration."""

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
    from homeassistant.core import callback
    from homeassistant.helpers import config_validation as cv

    PLATFORMS: list[Platform] = [Platform.SENSOR]
    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

except ImportError:  # pragma: no cover
    # Standalone test run, no Home Assistant installed
    PLATFORMS = []
    CONFIG_SCHEMA = {}  # type: ignore[assignment]


def _skip_runtime_setup() -> bool:
    """Return True when runtime setup should be skipped (test mode)."""
    return os.getenv("AFVALWIJZER_SKIP_INIT") == "1"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Afvalwijzer integration."""
    if _skip_runtime_setup():
        return True

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Afvalwijzer from a config entry."""
    if _skip_runtime_setup():
        return True

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "data": dict(entry.data),
        "options": dict(entry.options),
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


@callback
async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "data": dict(entry.data),
        "options": dict(entry.options),
    }
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Afvalwijzer config entry."""
    if _skip_runtime_setup():
        return True

    if not PLATFORMS:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
