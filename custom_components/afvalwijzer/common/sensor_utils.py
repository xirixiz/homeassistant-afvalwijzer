"""Shared sensor utility functions for Afvalwijzer.

Consolidates helper functions previously duplicated across sensor_custom.py
and sensor_provider.py: timezone handling, address formatting, unique ID
generation, value translation, and device info construction.
"""

from __future__ import annotations

from datetime import date, datetime, time
import hashlib
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from ..const.const import (
    CONF_COLLECTOR,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    CONF_TRANSLATE_STATES,
    DOMAIN,
)


def is_naive(value: datetime) -> bool:
    """Return True if the datetime is timezone-naive."""
    return value.tzinfo is None or value.tzinfo.utcoffset(value) is None


def as_utc_aware(value: datetime) -> datetime:
    """Return timezone aware datetime in UTC."""
    if is_naive(value):
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(value)


def date_to_local_midnight(value: date) -> datetime:
    """Convert a date into a timezone-aware local midnight datetime."""
    local_dt = datetime.combine(value, time.min).replace(
        tzinfo=dt_util.DEFAULT_TIME_ZONE
    )
    return local_dt


def address_key(config: dict[str, Any]) -> str:
    """Build a deterministic key from address components.

    Uses a filtered join to avoid trailing-colon collisions when
    optional fields (suffix, street_name) are empty.
    """
    postal_code = str(config.get(CONF_POSTAL_CODE, "")).strip().upper().replace(" ", "")
    house_number = str(config.get(CONF_HOUSE_NUMBER, "")).strip()
    suffix = str(config.get(CONF_SUFFIX, "")).strip().upper()
    street_name = str(config.get(CONF_STREET_NAME, "")).strip()

    parts = [postal_code, house_number, suffix, street_name]
    return ":".join(p for p in parts if p)


def address_label(config: dict[str, Any]) -> str:
    """Build a human-readable address label."""
    postal_code = str(config.get(CONF_POSTAL_CODE, "")).strip().upper().replace(" ", "")
    house_number = str(config.get(CONF_HOUSE_NUMBER, "")).strip()
    suffix = str(config.get(CONF_SUFFIX, "")).strip().upper()
    street_name = str(config.get(CONF_STREET_NAME, "")).strip()

    return f"{postal_code} {house_number}{suffix} {street_name}".strip()


def make_unique_id(config: dict[str, Any], waste_type: str) -> str:
    """Generate a stable unique ID for a sensor from its config and waste type."""
    unique_source = f"{waste_type}|{config.get(CONF_COLLECTOR)}|{address_key(config)}"
    return hashlib.sha1(unique_source.encode(), usedforsecurity=False).hexdigest()


def build_device_info(config: dict[str, Any]) -> DeviceInfo:
    """Build a DeviceInfo dict grouping sensors for the same address."""
    return DeviceInfo(
        identifiers={(DOMAIN, address_key(config))},
        name=f"Afvalwijzer {config.get(CONF_FRIENDLY_NAME) or address_label(config)}",
        manufacturer="Afvalwijzer",
        model=config.get(CONF_COLLECTOR),
        entry_type=DeviceEntryType.SERVICE,
    )


def translate_value(
    value: Any,
    config: dict[str, Any],
    coordinator: Any,
) -> Any:
    """Translate a raw waste type value using pre-loaded translation files.

    Returns the original value unchanged if translation is disabled or
    no match is found.
    """
    if not isinstance(value, str) or not value:
        return value

    if not config.get(CONF_TRANSLATE_STATES, False):
        return str(value)

    sensor_translations = getattr(coordinator, "sensor_translations", {})

    parts = [p.strip() for p in value.split(",")]
    translated_parts = []
    for part in parts:
        safe_part = part.lower().replace(" ", "_").replace("-", "_")
        translated_part = sensor_translations.get(safe_part, {}).get("name", part)
        translated_parts.append(translated_part)

    return ", ".join(translated_parts)


def parse_and_apply_value(
    value: Any,
) -> tuple[Any, SensorDeviceClass | None]:
    """Parse a raw string value into datetime/date if possible.

    Returns:
        A tuple of (parsed_value, None). The device_class is set by the
        caller based on their specific logic.

    """
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            return parsed, None
        parsed_date = dt_util.parse_date(value)
        if parsed_date is not None:
            return parsed_date, None

    return value, None
