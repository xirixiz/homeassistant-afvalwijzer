"""Afvalwijzer provider sensor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .common.sensor_utils import (
    address_key,
    as_utc_aware,
    build_device_info,
    date_to_local_midnight,
    icon_for_waste_type,
    make_unique_id,
    translate_value,
)
from .const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW,
    ATTR_IS_COLLECTION_DATE_TODAY,
    ATTR_IS_COLLECTION_DATE_TOMORROW,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_INCLUDE_TODAY,
    CONF_SHOW_FULL_TIMESTAMP,
    CONF_TRANSLATE_STATES,
    DEFAULT_INCLUDE_TODAY,
    DEFAULT_SHOW_FULL_TIMESTAMP,
    SENSOR_ICON,
    SENSOR_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Config:
    default_label: str
    include_today: bool
    show_full_timestamp: bool
    translate_states: bool


class ProviderSensor(CoordinatorEntity, SensorEntity):
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
            translate_states=bool(config.get(CONF_TRANSLATE_STATES, False)),
        )

        self._attr_has_entity_name = True
        self._attr_translation_key = waste_type.lower().replace("-", "_")

        addr = address_key(config)
        self.entity_id = f"sensor.{slugify(SENSOR_PREFIX + addr + '_' + waste_type)}"

        self._attr_unique_id = make_unique_id(config, waste_type)
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

    async def async_added_to_hass(self) -> None:
        """Populate initial state from data the coordinator already has."""
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    def _set_error_state(self) -> None:
        """Set sensor to error state."""
        if self._is_notification_sensor:
            self._native_value = 0
            self._fallback_state = "0"
        else:
            self._fallback_state = self._translate_value(str(self._cfg.default_label))
            self._native_value = None

        self._days_until_collection_date = None
        self._attr_device_class = None
        self._is_collection_date_today = False
        self._is_collection_date_tomorrow = False
        self._is_collection_date_day_after_tomorrow = False
        self._last_update = dt_util.now().isoformat()

    @property
    def device_info(self):
        """Group all sensors for the same address under one device."""
        return build_device_info(self._config)

    @staticmethod
    def _icon_for_waste_type(waste_type: str) -> str:
        icon = icon_for_waste_type(waste_type)
        if icon is None:
            _LOGGER.debug("No specific icon for: %s", waste_type)
            return SENSOR_ICON
        return icon

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
                if self._native_value is not None:
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
        return translate_value(value, self._config, self.coordinator)

    def _select_provider_data(self) -> dict[str, Any]:
        if self._cfg.include_today:
            return self.coordinator.waste_data_with_today or {}
        return self.coordinator.waste_data_without_today or {}

    def _apply_value(self, value: Any) -> None:
        self._days_until_collection_date = None
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
            aware = as_utc_aware(value)
            self._set_timestamp(aware)
            return

        if isinstance(value, date):
            aware = date_to_local_midnight(value)
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
