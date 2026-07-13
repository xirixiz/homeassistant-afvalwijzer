"""Afvalwijzer integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    DOMAIN,
    SENSOR_ICON,
    SENSOR_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE_TODAY = "include_today"
CONF_SHOW_FULL_TIMESTAMP = "show_full_timestamp"

DEFAULT_INCLUDE_TODAY = True
DEFAULT_SHOW_FULL_TIMESTAMP = True


@dataclass(slots=True)
class _Config:
    default_label: str
    include_today: bool
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
    house_number = str(config.get(CONF_HOUSE_NUMBER, "")).strip()
    suffix = str(config.get(CONF_SUFFIX, "")).strip().upper()
    street_name = str(config.get(CONF_STREET_NAME, "")).strip()

    return f"{postal_code}:{house_number}:{suffix}:{street_name}".strip(":")


def _address_label(config: dict[str, Any]) -> str:
    postal_code = str(config.get(CONF_POSTAL_CODE, "")).strip().upper().replace(" ", "")
    house_number = str(config.get(CONF_HOUSE_NUMBER, "")).strip()
    suffix = str(config.get(CONF_SUFFIX, "")).strip().upper()
    street_name = str(config.get(CONF_STREET_NAME, "")).strip()

    return f"{postal_code} {house_number}{suffix} {street_name}".strip()


class ProviderSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Representation of a provider based waste sensor."""

    def __init__(
        self,
        hass: Any,
        waste_type: str,
        coordinator: Any,
        config: dict[str, Any],
    ) -> None:
        """Initialize a provider-based Afvalwijzer sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self.waste_type = waste_type
        self.coordinator = coordinator
        self._config = config

        self._cfg = _Config(
            default_label=str(config.get(CONF_DEFAULT_LABEL, "geen")),
            include_today=self._resolve_include_today(config),
            show_full_timestamp=bool(
                config.get(CONF_SHOW_FULL_TIMESTAMP, DEFAULT_SHOW_FULL_TIMESTAMP)
            ),
        )

        self._attr_has_entity_name = True
        self._attr_translation_key = waste_type.lower().replace("-", "_")
        self.entity_id = f"sensor.{SENSOR_PREFIX}{waste_type}"
        self._attr_unique_id = self._make_unique_id(config, waste_type)
        self._attr_icon = self._icon_for_waste_type(waste_type)

        self._is_notification_sensor = waste_type == "notifications"
        self._last_update: str | None = None
        self._days_until_collection_date: int | None = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._attr_device_class: SensorDeviceClass | None = None
        self._native_value: datetime | int | None = None

        fallback_val = "0" if self._is_notification_sensor else self._cfg.default_label
        self._fallback_state = fallback_val

    def _set_error_state(self) -> None:
        """Set sensor to error state."""
        self._days_until_collection_date = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._attr_device_class = None
        self._native_value = None
        self._fallback_state = self._translate_value(str(self._cfg.default_label))

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors for the same address under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, _address_key(self._config))},
            name=f"Afvalwijzer {self._config.get(CONF_FRIENDLY_NAME) or _address_label(self._config)}",
            manufacturer="Afvalwijzer",
            model=self._config.get(CONF_COLLECTOR),
            entry_type="service",
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
            case "best-tas":
                return "mdi:bag-personal"
            case "gft":
                return "mdi:flower"
            case "glas":
                return "mdi:glass-fragile"
            case "grofvuil":
                return "mdi:sofa"
            case "kerstbomen":
                return "mdi:pine-tree"
            case "grip" | "maas" | "milieubus":
                return "mdi:truck-cargo-container"
            case "papier":
                return "mdi:newspaper"
            case "plastic" | "pmd":
                return "mdi:bottle-soda-classic"
            case "restafval" | "restwagen":
                return "mdi:trash-can"
            case "restafvalzakken":
                return "mdi:sack"
            case "snoeiafval" | "tuinafval":
                return "mdi:leaf"
            case "notifications":
                return "mdi:bell"
            case _:
                _LOGGER.debug("No specific icon for: %s", waste_type)
                return SENSOR_ICON

    @staticmethod
    def _resolve_include_today(config: dict[str, Any]) -> bool:
        """Resolve include_today from options, else fall back to legacy setting."""
        if CONF_INCLUDE_TODAY in config:
            return bool(config.get(CONF_INCLUDE_TODAY, DEFAULT_INCLUDE_TODAY))

        raw = str(config.get(CONF_EXCLUDE_PICKUP_TODAY, "true")).lower()
        exclude_today = raw in ("true", "yes", "1", "on")
        return not exclude_today

    @property
    def native_value(self) -> datetime | int | str | None:
        """Return provider data based on include_today setting."""
        if self._is_notification_sensor:
            return self._native_value if isinstance(self._native_value, int) else 0

        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            return (
                self._native_value if isinstance(self._native_value, datetime) else None
            )

        return self._fallback_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Apply provider data to the sensor state."""
        base_attrs: dict[str, Any] = {
            ATTR_LAST_UPDATE: self._last_update,
            "collector": self._config.get(CONF_COLLECTOR),
        }

        if self._is_notification_sensor:
            notifications = self.coordinator.notification_data or []
            base_attrs["notifications"] = notifications
            base_attrs["count"] = len(notifications)
            return base_attrs

        base_attrs.update(
            {
                ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date,
                ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today,
                ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow,
                ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: self._is_collection_date_day_after_tomorrow,
            }
        )
        return base_attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Updating sensor from coordinator: %s", self.entity_id)

        try:
            if self._is_notification_sensor:
                self._update_notification_sensor()
            else:
                waste_data_provider = self._select_provider_data()
                if self.waste_type not in waste_data_provider:
                    raise ValueError(f"No data for waste type: {self.waste_type}")

                self._apply_value(waste_data_provider[self.waste_type])
                if "None" not in str(self._native_value):
                    _LOGGER.debug(
                        "Sensor %s updated. Value: %s",
                        self.entity_id,
                        self._native_value,
                    )
                self._last_update = dt_util.now().isoformat()
        except Exception as err:
            _LOGGER.error("Error updating sensor %s: %s", self.entity_id, err)
            self._set_error_state()

        self.async_write_ha_state()

    def _translate_value(self, value: Any) -> Any:
        """Translate the raw waste type value using the pre-loaded translation files."""
        if not isinstance(value, str) or not value:
            return value

        sensor_translations = getattr(self.coordinator, "sensor_translations", {})

        parts = [p.strip() for p in value.split(",")]
        translated_parts = []
        for part in parts:
            safe_part = part.lower().replace(" ", "_").replace("-", "_")
            translated_part = sensor_translations.get(safe_part, {}).get("name", part)
            translated_parts.append(translated_part)

        return ", ".join(translated_parts)

    def _select_provider_data(self) -> dict[str, Any]:
        if self._cfg.include_today:
            return self.coordinator.waste_data_with_today or {}
        return self.coordinator.waste_data_without_today or {}

    def _apply_value(self, value: Any) -> None:
        self._days_until_collection_date = self._cfg.default_label
        self._attr_device_class = None
        self._native_value = None

        if isinstance(value, str):
            parsed = dt_util.parse_datetime(value)
            if parsed is not None:
                value = parsed
            else:
                parsed_date = dt_util.parse_date(value)
                if parsed_date is not None:
                    value = parsed_date

        if isinstance(value, datetime):
            aware = _as_utc_aware(value)
            self._set_timestamp(aware)
            return

        if isinstance(value, date):
            aware = _date_to_local_midnight(value)
            self._set_timestamp(aware, date_value=value)
            return

        self._fallback_state = self._translate_value(str(value))
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False

    def _set_timestamp(
        self, aware_utc: datetime, *, date_value: date | None = None
    ) -> None:
        local_dt = aware_utc.astimezone(dt_util.DEFAULT_TIME_ZONE)
        collection_date = date_value or local_dt.date()

        self._update_collection_date_flags(collection_date)

        today = dt_util.now().date()
        self._days_until_collection_date = (collection_date - today).days

        if self._cfg.show_full_timestamp:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._native_value = local_dt
            return

        self._attr_device_class = None
        self._fallback_state = collection_date.isoformat()

    def _update_collection_date_flags(self, collection_date: date) -> None:
        today = dt_util.now().date()
        self._is_collection_date_today = collection_date == today
        self._is_collection_date_tomorrow = collection_date == (
            today + timedelta(days=1)
        )
        self._is_collection_date_day_after_tomorrow = collection_date == (
            today + timedelta(days=2)
        )

    def _update_notification_sensor(self) -> None:
        notifications = self.coordinator.notification_data or []
        count = len(notifications)

        self._native_value = count
        self._fallback_state = str(count)

        self._attr_icon = "mdi:bell-alert" if count > 0 else "mdi:bell"
        self._last_update = dt_util.now().isoformat()

        _LOGGER.debug("Notification sensor updated: %s notification(s)", count)

    def _set_error_state(self) -> None:
        if self._is_notification_sensor:
            self._native_value = 0
            self._fallback_state = "0"
        else:
            self._fallback_state = self._cfg.default_label
            self._native_value = None

        self._days_until_collection_date = None
        self._attr_device_class = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._last_update = dt_util.now().isoformat()
