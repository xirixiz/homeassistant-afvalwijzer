"""Afvalwijzer integration."""

from __future__ import annotations

import json
import logging
import os
import pathlib
from random import randint
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later, async_track_time_change

from .const.const import (
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    DOMAIN,
)
from .coordinator import AfvalwijzerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Options keys
CONF_INCLUDE_TODAY = "include_today"
CONF_SHOW_FULL_TIMESTAMP = "show_full_timestamp"

DEFAULT_INCLUDE_TODAY = True
DEFAULT_SHOW_FULL_TIMESTAMP = True
DEFAULT_DEFAULT_LABEL = "geen"
DEFAULT_EXCLUDE_LIST = ""

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

try:
    from homeassistant.const import Platform
    from homeassistant.helpers import config_validation as cv

    PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]
    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
except ImportError:  # pragma: no cover
    # Standalone test run, no Home Assistant installed
    PLATFORMS = []
    CONFIG_SCHEMA = {}  # type: ignore[assignment]


def _skip_runtime_setup() -> bool:
    """Return True when runtime setup should be skipped (test mode)."""
    return os.getenv("AFVALWIJZER_SKIP_INIT") == "1"


def _derive_include_today_from_legacy(entry: ConfigEntry) -> bool:
    raw = entry.data.get(CONF_EXCLUDE_PICKUP_TODAY)
    if raw is None:
        return DEFAULT_INCLUDE_TODAY

    raw_str = str(raw).lower()
    exclude_today = raw_str in ("true", "yes", "1", "on")
    return not exclude_today


def _migrate_options_if_needed(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Ensure required options exist, migrating from legacy entry.data if needed."""
    options: dict[str, Any] = dict(entry.options)
    changed = False

    if CONF_INCLUDE_TODAY not in options:
        options[CONF_INCLUDE_TODAY] = _derive_include_today_from_legacy(entry)
        changed = True

    if CONF_SHOW_FULL_TIMESTAMP not in options:
        options[CONF_SHOW_FULL_TIMESTAMP] = DEFAULT_SHOW_FULL_TIMESTAMP
        changed = True

    if CONF_DEFAULT_LABEL not in options:
        options[CONF_DEFAULT_LABEL] = str(
            entry.data.get(CONF_DEFAULT_LABEL, DEFAULT_DEFAULT_LABEL)
        )
        changed = True

    if CONF_EXCLUDE_LIST not in options:
        options[CONF_EXCLUDE_LIST] = str(
            entry.data.get(CONF_EXCLUDE_LIST, DEFAULT_EXCLUDE_LIST)
        )
        changed = True

    if changed:
        hass.config_entries.async_update_entry(entry, options=options)

    return options


def _build_effective_config(
    entry: ConfigEntry, options: dict[str, Any]
) -> dict[str, Any]:
    """Merge entry data and options, with options taking precedence."""
    return {**dict(entry.data), **options}


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

    options = _migrate_options_if_needed(hass, entry)
    effective_config = _build_effective_config(entry, options)

    coordinator = AfvalwijzerDataUpdateCoordinator(
        hass, effective_config, entry.entry_id
    )

    # Pre-load translations to avoid blocking I/O in sensor callbacks
    lang = effective_config.get("language", "nl")

    def _load_translations():
        trans_path = pathlib.Path(__file__).parent / "translations" / f"{lang}.json"
        try:
            with open(trans_path, encoding="utf-8") as f:
                return json.load(f).get("entity", {}).get("sensor", {})
        except Exception:
            return {}

    coordinator.sensor_translations = await hass.async_add_executor_job(
        _load_translations
    )

    cache_loaded = await coordinator.async_load_cache()

    if not cache_loaded:
        await coordinator.async_config_entry_first_refresh()
    else:
        hass.async_create_task(coordinator.async_request_refresh())

    hass.data[DOMAIN][entry.entry_id] = {
        "data": dict(entry.data),
        "options": options,
        "config": effective_config,
        "coordinator": coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _schedule_midnight_update(now: Any) -> None:
        """Trigger an update at midnight with a randomized jitter."""
        jitter = randint(1, 600)
        _LOGGER.debug("Scheduling midnight refresh in %s seconds", jitter)

        async def _do_update(_: Any) -> None:
            await coordinator.async_request_refresh()

        entry.async_on_unload(async_call_later(hass, jitter, _do_update))

    entry.async_on_unload(
        async_track_time_change(
            hass, _schedule_midnight_update, hour=0, minute=0, second=0
        )
    )

    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
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
