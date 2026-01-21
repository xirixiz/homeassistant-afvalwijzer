"""Afvalwijzer integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const.const import (
    _LOGGER,
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_ID,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    SENSOR_ICON,
    SENSOR_PREFIX,
)

# Options keys from config flow
CONF_INCLUDE_TODAY = "include_today"
CONF_SHOW_FULL_TIMESTAMP = "show_full_timestamp"

DEFAULT_INCLUDE_TODAY = True
DEFAULT_SHOW_FULL_TIMESTAMP = True


@dataclass(slots=True)
class _Config:
    default_label: str
    date_isoformat: bool
    include_today: bool
    show_full_timestamp: bool
    id_name: str


def _as_utc_aware(value: datetime) -> datetime:
    """Return timezone aware datetime in UTC."""
    if dt_util.is_naive(value):
        value = dt_util.DEFAULT_TIME_ZONE.localize(value)
    return dt_util.as_utc(value)

def _date_to_local_midnight(value: date) -> datetime:
    """Convert a date into a timezone-aware local midnight datetime."""
    local_dt = datetime.combine(value, time.min)
    return dt_util.DEFAULT_TIME_ZONE.localize(local_dt)


class ProviderSensor(RestoreEntity, SensorEntity):
    """Representation of a provider based waste sensor."""

    def __init__(
        """Initialize a provider-based Afvalwijzer sensor."""
        self,
        hass: Any,
        waste_type: str,
        fetch_data: Any,
        config: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.waste_type = waste_type
        self.fetch_data = fetch_data

        id_name = str(config.get(CONF_ID, "") or "")
        self._cfg = _Config(
            default_label=str(config.get(CONF_DEFAULT_LABEL, "geen")),
            date_isoformat=bool(config.get(CONF_DATE_ISOFORMAT, False)),
            include_today=self._resolve_include_today(config),
            show_full_timestamp=bool(
                config.get(CONF_SHOW_FULL_TIMESTAMP, DEFAULT_SHOW_FULL_TIMESTAMP)
            ),
            id_name=id_name,
        )

        self._attr_name = (
            SENSOR_PREFIX + (f"{self._cfg.id_name} " if self._cfg.id_name else "")
        ) + waste_type

        self._attr_unique_id = self._make_unique_id(config, waste_type)

        self._is_notification_sensor = waste_type == "notifications"
        self._attr_icon = (
            "mdi:bell-outline" if self._is_notification_sensor else SENSOR_ICON
        )

        self._last_update: str | None = None
        self._days_until_collection_date: int | None = None
        self._is_collection_date_today: bool = False
        self._is_collection_date_tomorrow: bool = False
        self._is_collection_date_day_after_tomorrow: bool = False

        self._attr_device_class: SensorDeviceClass | None = None
        self._native_value: datetime | int | None = None
        self._fallback_state: str = (
            "0" if self._is_notification_sensor else self._cfg.default_label
        )

    @staticmethod
    def _make_unique_id(config: dict[str, Any], waste_type: str) -> str:
        unique_source = (
            f"{waste_type}"
            f"{config.get(CONF_ID)}"
            f"{config.get(CONF_COLLECTOR)}"
            f"{config.get(CONF_POSTAL_CODE)}"
            f"{config.get(CONF_STREET_NUMBER)}"
            f"{config.get(CONF_SUFFIX, '')}"
        )
        return hashlib.sha1(unique_source.encode()).hexdigest()

    @staticmethod
    def _resolve_include_today(config: dict[str, Any]) -> bool:
        """Resolve include_today from options, else fall back to legacy setting."""
        if CONF_INCLUDE_TODAY in config:
            return bool(config.get(CONF_INCLUDE_TODAY, DEFAULT_INCLUDE_TODAY))

        # Backward compatible: exclude_pickup_today True means do NOT include today
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
        if self._is_notification_sensor:
            notifications = self.fetch_data.notification_data or []
            return {
                ATTR_LAST_UPDATE: self._last_update,
                "notifications": notifications,
                "count": len(notifications),
            }

        return {
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_DAYS_UNTIL_COLLECTION_DATE: self._days_until_collection_date,
            ATTR_IS_COLLECTION_DATE_TODAY: self._is_collection_date_today,
            ATTR_IS_COLLECTION_DATE_TOMORROW: self._is_collection_date_tomorrow,
            ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW: (
                self._is_collection_date_day_after_tomorrow
            ),
        }

    async def async_update(self) -> None:
        """Set the sensor state as a timestamp value."""
        _LOGGER.debug("Updating sensor: %s", self.name)

        try:
            await self.hass.async_add_executor_job(self.fetch_data.update)

            if self._is_notification_sensor:
                self._update_notification_sensor()
                return

            waste_data_provider = self._select_provider_data()
            if self.waste_type not in waste_data_provider:
                raise ValueError(f"No data for waste type: {self.waste_type}")

            self._apply_value(waste_data_provider[self.waste_type])
            self._last_update = dt_util.now().isoformat()

        except Exception as err:
            _LOGGER.error("Error updating sensor %s: %s", self.name, err)
            self._set_error_state()

    def _select_provider_data(self) -> dict[str, Any]:
        if self._cfg.include_today:
            return self.fetch_data.waste_data_with_today or {}
        return self.fetch_data.waste_data_without_today or {}

    def _apply_value(self, value: Any) -> None:
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

        # If not showing full timestamp, expose date as string instead
        self._attr_device_class = None
        if self._cfg.date_isoformat:
            self._fallback_state = collection_date.isoformat()
        else:
            self._fallback_state = str(collection_date)

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
        notifications = self.fetch_data.notification_data or []
        count = len(notifications)

        self._native_value = count
        self._fallback_state = str(count)

        self._attr_icon = "mdi:bell-alert" if count > 0 else "mdi:bell-outline"
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
