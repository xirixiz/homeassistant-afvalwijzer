"""Afvalwijzer integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_FRIENDLY_NAME,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    DOMAIN,
    SENSOR_ICON,
    SENSOR_PREFIX,
)

CONF_SHOW_FULL_TIMESTAMP = "show_full_timestamp"
DEFAULT_SHOW_FULL_TIMESTAMP = True


@dataclass(slots=True)
class _Config:
    default_label: str
    show_full_timestamp: bool


def _is_naive(value: datetime) -> bool:
    return value.tzinfo is None or value.tzinfo.utcoffset(value) is None


def _as_utc_aware(value: datetime) -> datetime:
    """Return timezone aware datetime in UTC."""
    if _is_naive(value):
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(value)


def _date_to_local_midnight(value: date) -> datetime:
    """Convert a date into a timezone-aware local midnight datetime."""
    local_dt = datetime.combine(value, time.min).replace(
        tzinfo=dt_util.DEFAULT_TIME_ZONE
    )
    return local_dt


def _address_key(config: dict[str, Any]) -> str:
    postal_code = str(config.get(CONF_POSTAL_CODE, "")).strip().upper().replace(" ", "")
    street_number = str(config.get(CONF_STREET_NUMBER, "")).strip()
    suffix = str(config.get(CONF_SUFFIX, "")).strip().upper()
    street_name = str(config.get(CONF_STREET_NAME, "")).strip()

    return f"{postal_code}:{street_number}:{suffix}:{street_name}".strip(":")


def _address_label(config: dict[str, Any]) -> str:
    postal_code = str(config.get(CONF_POSTAL_CODE, "")).strip().upper().replace(" ", "")
    street_number = str(config.get(CONF_STREET_NUMBER, "")).strip()
    suffix = str(config.get(CONF_SUFFIX, "")).strip().upper()
    street_name = str(config.get(CONF_STREET_NAME, "")).strip()

    return f"{postal_code} {street_number}{suffix} {street_name}".strip()


class CustomSensor(RestoreEntity, SensorEntity):
    """Representation of a custom based waste sensor."""

    def __init__(
        self,
        hass: Any,
        waste_type: str,
        fetch_data: Any,
        config: dict[str, Any],
    ) -> None:
        """Initialize a custom Afvalwijzer sensor."""
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data
        self._config = config

        self._cfg = _Config(
            default_label=str(config.get(CONF_DEFAULT_LABEL, "geen")),
            show_full_timestamp=bool(
                config.get(CONF_SHOW_FULL_TIMESTAMP, DEFAULT_SHOW_FULL_TIMESTAMP)
            ),
        )

        self._last_update: str | None = None
        self._days_until_collection_date: int | None = None

        self._attr_name = f"{SENSOR_PREFIX}{waste_type}"
        self._attr_unique_id = self._make_unique_id(config, waste_type)
        self._attr_icon = self._icon_for_waste_type(waste_type)

        self._attr_device_class: SensorDeviceClass | None = None
        self._native_value: datetime | str | None = None
        self._fallback_state = self._cfg.default_label

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors for the same address under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, _address_key(self._config))},
            name=f"Afvalwijzer {self._config.get(CONF_FRIENDLY_NAME) or _address_label(self._config)}",
            manufacturer="Afvalwijzer",
        )

    @staticmethod
    def _make_unique_id(config: dict[str, Any], waste_type: str) -> str:
        unique_source = (
            f"{waste_type}|{config.get(CONF_COLLECTOR)}|{_address_key(config)}"
        )
        return hashlib.sha1(unique_source.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def _icon_for_waste_type(waste_type: str) -> str:
        match waste_type:
            case "today":
                return "mdi:calendar-today"
            case "tomorrow":
                return "mdi:calendar"
            case "day_after_tomorrow":
                return "mdi:calendar-end"
            case "next_date":
                return "mdi:calendar-multiselect"
            case "next_in_days":
                return "mdi:counter"
            case _:
                _LOGGER.debug("No specific icon for: %s", waste_type)
                return SENSOR_ICON

    @property
    def native_value(self) -> datetime | str | None:
        """Return the native value of the sensor."""
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            return (
                self._native_value if isinstance(self._native_value, datetime) else None
            )
        return self._fallback_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Apply the fetched value to the sensor state."""
        attrs: dict[str, Any] = {
            ATTR_LAST_UPDATE: self._last_update,
            "collector": self._config.get(CONF_COLLECTOR),
        }
        if "next_date" in (self._attr_name or "").lower():
            attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] = self._days_until_collection_date
        return attrs

    async def async_update(self) -> None:
        """Fetch the latest data and update the state."""
        _LOGGER.debug("Updating custom sensor: %s", self.name)

        try:
            await self.hass.async_add_executor_job(self.fetch_data.update)
            waste_data_custom = self.fetch_data.waste_data_custom or {}

            if self.waste_type not in waste_data_custom:
                raise ValueError(f"No data for waste type: {self.waste_type}")

            self._apply_value(waste_data_custom[self.waste_type])
            self._last_update = dt_util.now().isoformat()

        except Exception as err:
            _LOGGER.error("Error updating custom sensor %s: %s", self.name, err)
            self._set_error_state()

    def _apply_value(self, value: Any) -> None:
        """Apply collector output to sensor state."""
        self._days_until_collection_date = None
        self._attr_device_class = None
        self._native_value = None

        if isinstance(value, datetime):
            aware = _as_utc_aware(value)
            self._set_timestamp(aware)
            return

        if isinstance(value, date):
            aware = _date_to_local_midnight(value)
            self._set_timestamp(aware, date_value=value)
            return

        self._fallback_state = str(value)

    def _set_timestamp(
        self, aware_utc: datetime, *, date_value: date | None = None
    ) -> None:
        """Set the sensor as a timestamp sensor."""
        local_dt = aware_utc.astimezone(dt_util.DEFAULT_TIME_ZONE)
        collection_date = date_value or local_dt.date()

        today = dt_util.now().date()
        self._days_until_collection_date = (collection_date - today).days

        if self._cfg.show_full_timestamp:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._native_value = local_dt
            return

        self._attr_device_class = None
        self._native_value = None
        self._fallback_state = collection_date.isoformat()

    def _set_error_state(self) -> None:
        """Set a safe fallback state on errors."""
        self._fallback_state = self._cfg.default_label
        self._days_until_collection_date = None
        self._attr_device_class = None
        self._native_value = None
        self._last_update = dt_util.now().isoformat()
