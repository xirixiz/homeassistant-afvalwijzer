
from __future__ import annotations

import os

if os.getenv("AFVALWIJZER_SKIP_INIT") == "1":
    pass
else:
    try:
        from homeassistant.config_entries import ConfigEntry
        from homeassistant.core import HomeAssistant
        from homeassistant.const import Platform
        from homeassistant.helpers.typing import ConfigType

        from .const.const import DOMAIN

        PLATFORMS: list[Platform] = [Platform.SENSOR]


        async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
            """Set up the Afvalwijzer integration."""
            hass.data.setdefault(DOMAIN, {})
            return True


        async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
            """Set up Afvalwijzer from a config entry."""
            hass.data.setdefault(DOMAIN, {})
            hass.data[DOMAIN][entry.entry_id] = entry.data
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            return True


        async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
            """Unload a config entry."""
            unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
            if unload_ok:
                hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
            return unload_ok

    except ModuleNotFoundError:
        pass